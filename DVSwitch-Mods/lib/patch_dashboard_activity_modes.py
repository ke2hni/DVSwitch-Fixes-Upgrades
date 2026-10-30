#!/usr/bin/env python3
# Version: 1.0.1
# SPDX-License-Identifier: MIT

"""Preserve MMDVM milliseconds and label Gateway DMR rows from BM/TGIF events."""

from __future__ import annotations

import argparse
from pathlib import Path
import re

FUNCTIONS_MARKER = "// DVSwitch-Mods: retain MMDVM log millisecond timestamps v1"
LOCAL_TX_MARKER = "// DVSwitch-Mods: local TX duration and unavailable metrics v1"
OLD_MARKER = "// DVSwitch-Mods: dashboard activity network labels v1"
LH_MARKER = "// DVSwitch-Mods: Gateway Activity DMR network labels v1"
INCLUDE = "include_once dirname(dirname(__FILE__)).'/include/dvswitch_mods_activity_mode.php';"
ORIGINAL_CELL = 'echo"<td align=\\"left\\" style=\\"color:green; font-weight:bold;\\">&nbsp;$listElem[1]</td>";'
UNPADDED_CELL = ORIGINAL_CELL.replace(">&nbsp;$listElem[1]", ">$listElem[1]")
OLD_BEFORE = "$dvsModsActivityOriginalMode = $listElem[1];\n$listElem[1] = dvsModsActivityModeLabel($listElem[1], $listElem[0]);\n"
OLD_AFTER = "\n$listElem[1] = $dvsModsActivityOriginalMode;"
NEW_BEFORE = "$dvsModsActivityOriginalMode = $listElem[1];\n$listElem[1] = dvsModsActivityModeLabel($listElem[1], $listElem[0], $listElem[5]);\n"
NEW_AFTER = OLD_AFTER
LOG_LINE_VARIABLE = "$logLine"


class PatchError(RuntimeError):
    pass


def patch_functions(text: str) -> str:
    if text.count(FUNCTIONS_MARKER) > 1:
        raise PatchError("duplicate MMDVM millisecond timestamp marker in functions.php")
    start = text.find("function getHeardList(")
    end = text.find("function getLastHeard(", start + 1)
    if start < 0 or end < 0:
        raise PatchError("could not locate getHeardList() in functions.php")
    region = text[start:end]
    # Keep millisecond log times and add one guarded local-TX duration path,
    # migrating both stock and previously patched dashboard functions.php.
    if FUNCTIONS_MARKER not in text:
        old_parser = "$timestamp = substr($logLines, 3, 19);"
        parser_variable = "$logLines" if region.count(old_parser) == 2 else LOG_LINE_VARIABLE
        old_parser = f"$timestamp = substr({parser_variable}, 3, 19);"
        new_parser = f"$timestamp = substr({parser_variable}, 3, 23);"
        if region.count(old_parser) != 2:
            raise PatchError("expected exactly two original activity timestamp parsers in getHeardList()")
        region = region.replace(old_parser, new_parser)
        text = text[:start] + region + text[end:]
        text = text.replace("function getHeardList(", FUNCTIONS_MARKER + "\nfunction getHeardList(", 1)
    else:
        start = text.find("function getHeardList(")
        end = text.find("function getLastHeard(", start + 1)
        region = text[start:end]
        if re.search(r"\$timestamp = substr\(\$logLines?, 3, 19\);", region) or len(re.findall(r"\$timestamp = substr\(\$logLines?, 3, 23\);", region)) != 2:
            raise PatchError("partial MMDVM millisecond timestamp modification in functions.php")

    if text.count(LOCAL_TX_MARKER) == 1:
        if "dvsModsLocalTxDuration" not in region or "$dvsModsLocalTxEndByMode" not in region:
            raise PatchError("partial local transmission duration modification in functions.php")
        return text
    if text.count(LOCAL_TX_MARKER) > 0:
        raise PatchError("duplicate local transmission duration marker in functions.php")
    helper = '''// DVSwitch-Mods: local TX duration helper v1
function dvsModsLocalTxDuration($start, $end = null) {
    $utc = new DateTimeZone('UTC');
    $parse = function ($value) use ($utc) {
        if (!preg_match('/^(\\d{4}-\\d\\d-\\d\\d \\d\\d:\\d\\d:\\d\\d)(?:\\.(\\d{1,6}))?$/D', (string)$value, $parts)) { return false; }
        $fraction = isset($parts[2]) ? str_pad($parts[2], 6, '0') : '000000';
        return DateTimeImmutable::createFromFormat('!Y-m-d H:i:s.u', $parts[1].'.'.$fraction, $utc);
    };
    $begin = $parse($start);
    $finish = $end === null ? new DateTimeImmutable('now', $utc) : $parse($end);
    if ($begin === false || $finish === false) { return '0.0'; }
    $seconds = (float)$finish->format('U.u') - (float)$begin->format('U.u');
    return number_format(max(0, $seconds), 1, '.', '');
}
'''
    if "function dvsModsLocalTxDuration(" not in text:
        text = text.replace("function getHeardList(", LOCAL_TX_MARKER + "\n" + helper + "\nfunction getHeardList(", 1)
    elif "// DVSwitch-Mods: local TX duration helper v1" not in text:
        raise PatchError("unmarked local transmission duration helper in functions.php")
    start = text.find("function getHeardList(")
    end = text.find("function getLastHeard(", start + 1)
    region = text[start:end]
    loop_anchor = "\tforeach ($logLines as $logLine) {"
    if region.count(loop_anchor) != 1:
        raise PatchError("could not locate the unique getHeardList() log loop")
    region = region.replace(loop_anchor, "\t$dvsModsLocalTxEndByMode = array();\n" + loop_anchor, 1)
    loop_init = loop_anchor + "\n"
    if region.count(loop_init) != 1:
        raise PatchError("could not locate the unique log-loop initialization point")
    region = region.replace(loop_init, loop_init + "\t\t$dvsModsLocalTxDuration = null;\n", 1)
    off_anchor = '\t\tif (strpos($logLine,"TX state = OFF")){\n\t\t\t$dvsm=substr($logLine, 27, strpos($logLine,",") - 27);'
    off_new = off_anchor + '''
            $dvsModsTxFrameDuration = null;
            if ($dvsm === "DMR" && preg_match('/DMR frame count was\\s+([0-9]+)\\s+frames/', $logLine, $dvsModsTxFrames)) {
                $dvsModsTxFrameDuration = number_format(((int)$dvsModsTxFrames[1]) * 0.059, 1, '.', '');
            }
            $dvsModsLocalTxEndByMode[$dvsm] = array(substr($logLine, 3, 23), $dvsModsTxFrameDuration);'''
    if "$dvsModsTxFrameDuration" not in region:
        if region.count(off_anchor) != 1:
            raise PatchError("TX end parser is missing or ambiguous in functions.php")
        region = region.replace(off_anchor, off_new, 1)
    elif region.count("$dvsModsLocalTxEndByMode[$dvsm]") != 1:
        raise PatchError("local TX end-time tracking is incomplete in functions.php")
    begin_anchor = '\t\tif (strpos($logLine,"Begin TX")) {\n\t\t$mode = substr($logLine, 27, strpos($logLine,",") - 27);'
    begin_new = begin_anchor + '''
            $dvsModsTxBegin = substr($logLine, 3, 23);
            if (isset($dvsModsLocalTxEndByMode[$mode])) {
                $dvsModsTxEnd = $dvsModsLocalTxEndByMode[$mode];
                $dvsModsLocalTxDuration = $dvsModsTxEnd[1] !== null ? $dvsModsTxEnd[1] : dvsModsLocalTxDuration($dvsModsTxBegin, $dvsModsTxEnd[0]);
                unset($dvsModsLocalTxEndByMode[$mode]);
            } else {
                $dvsModsLocalTxDuration = dvsModsLocalTxDuration($dvsModsTxBegin);
            }'''
    if region.count("$dvsModsTxBegin = substr($logLine, 3, 23);") == 0:
        if region.count(begin_anchor) != 1:
            raise PatchError("Begin TX parser is missing or ambiguous in functions.php")
        region = region.replace(begin_anchor, begin_new, 1)
    elif region.count("$dvsModsTxBegin = substr($logLine, 3, 23);") != 1:
        raise PatchError("duplicate local TX duration calculation in functions.php")
    row_anchor = "\t\t// Callsign or ID should be less than 11 chars long, otherwise it could be errorneous"
    row_new = '''\t\t// Local TX has no measured RF Loss/BER fields; show the requested zero values and calculated duration.
\t\tif ($source === "LNet" && $dvsModsLocalTxDuration !== null) {
\t\t\t$duration = $dvsModsLocalTxDuration;
\t\t\t$loss = "0%";
\t\t\t$ber = "0.0%";
\t\t}
''' + row_anchor
    if row_new not in region:
        if region.count(row_anchor) != 1:
            raise PatchError("activity row insertion point is missing or ambiguous in functions.php")
        region = region.replace(row_anchor, row_new, 1)
    return text[:start] + region + text[end:]


def _remove_old_wrapper(text: str, name: str) -> str:
    cells = (ORIGINAL_CELL, UNPADDED_CELL)
    matches = [cell for cell in cells if text.count(OLD_BEFORE + cell + OLD_AFTER) == 1]
    if len(matches) != 1:
        raise PatchError(f"legacy activity-mode wrapper is missing or ambiguous in {name}")
    wrapped = OLD_BEFORE + matches[0] + OLD_AFTER
    return text.replace(wrapped, matches[0], 1)


def patch_lh(text: str) -> str:
    if text.count(LH_MARKER) == 1:
        if text.count(INCLUDE) != 1 or text.count(NEW_BEFORE) != 1 or OLD_MARKER in text:
            raise PatchError("incomplete or ambiguous Gateway Activity DMR label patch")
        return text
    if text.count(LH_MARKER) > 1:
        raise PatchError("duplicate Gateway Activity DMR label marker")

    if OLD_MARKER in text:
        if text.count(OLD_MARKER) != 1:
            raise PatchError("duplicate legacy activity-mode marker in lh.php")
        text = _remove_old_wrapper(text, "lh.php")
        text = text.replace(OLD_MARKER, LH_MARKER, 1)
    else:
        if "dvsModsActivityModeLabel(" in text:
            raise PatchError("unmarked or partial activity-mode wrapper in lh.php")
        if not text.startswith("<?php\n"):
            raise PatchError("unsupported PHP opening in lh.php")
        text = text.replace("<?php\n", "<?php\n" + LH_MARKER + "\n", 1)

    if text.count(INCLUDE) == 0:
        anchors = (
            "include_once dirname(dirname(__FILE__)).'/include/dvswitch_mods_target_display.php';",
            "include_once dirname(dirname(__FILE__)).'/include/dvswitch_mods_fcc_first_names.php';",
            "include_once dirname(dirname(__FILE__)).'/include/functions.php';",
        )
        anchor = next((item for item in anchors if text.count(item) == 1), None)
        if anchor is None:
            raise PatchError("could not find a unique helper include anchor in lh.php")
        text = text.replace(anchor, anchor + "\n" + INCLUDE, 1)
    if text.count(INCLUDE) != 1:
        raise PatchError("activity helper include is ambiguous in lh.php")

    cells = (ORIGINAL_CELL, UNPADDED_CELL)
    found = [cell for cell in cells if text.count(cell) == 1]
    if len(found) != 1:
        raise PatchError("could not find the original Gateway Activity Mode cell exactly once")
    cell = found[0]
    return text.replace(cell, NEW_BEFORE + cell + NEW_AFTER, 1)


def clean_localtx(text: str) -> str:
    if OLD_MARKER not in text:
        if "dvsModsActivityModeLabel(" in text:
            raise PatchError("unmarked or partial legacy activity-mode wrapper in localtx.php")
        return text
    if text.count(OLD_MARKER) != 1:
        raise PatchError("duplicate legacy activity-mode marker in localtx.php")
    text = _remove_old_wrapper(text, "localtx.php")
    text = text.replace(OLD_MARKER + "\n", "", 1)
    if text.count(INCLUDE) != 1:
        raise PatchError("legacy activity helper include is missing or ambiguous in localtx.php")
    return text.replace(INCLUDE + "\n", "", 1)


def patch_file(path: Path, transform) -> None:
    raw = path.read_bytes()
    if b"\r" in raw.replace(b"\r\n", b""):
        raise PatchError(f"unsupported mixed line endings in {path}")
    newline = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8").replace("\r\n", "\n")
    path.write_bytes(transform(text).replace("\n", newline).encode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--functions", type=Path, required=True)
    parser.add_argument("--lh", type=Path, required=True)
    parser.add_argument("--localtx", type=Path, required=True)
    args = parser.parse_args()
    patch_file(args.functions, patch_functions)
    patch_file(args.lh, patch_lh)
    patch_file(args.localtx, clean_localtx)


if __name__ == "__main__":
    try:
        main()
    except (OSError, UnicodeError, PatchError) as error:
        raise SystemExit(f"ERROR: {error}")
