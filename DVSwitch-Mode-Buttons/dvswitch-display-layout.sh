#!/usr/bin/env bash
set -u

VERSION="1.3.4"
ROOT="/usr/share/dvswitch"

STAMP="$(date +%Y%m%d-%H%M%S)"
ORIGINAL_BACKUP_DIR="$ROOT/.dvs-dashboard-display-original"
RUN_BACKUP_DIR="$ROOT/.dvs-dashboard-display-backup-$STAMP"
LOG_FILE="$HOME/dvs-dashboard-display-$STAMP.log"

INDEX_FILE="$ROOT/index.php"
CSS_FILE="$ROOT/css/css.php"
LH_FILE="$ROOT/include/lh.php"
LOCALTX_FILE="$ROOT/include/localtx.php"
SYSTEM_FILE="$ROOT/include/system.php"

# Keep supported overlays explicit so upgrades and restores recognize each layout version.
CSS_LAYOUT_OVERLAY_V130='/* DVSwitch-Mods: responsive column alignment and compact header v1.3.0 */ .nav #modeInfo > fieldset { margin-top:15px !important; } .header { padding:0; } .header h2 { margin:8px 0; } .container {'
CSS_LAYOUT_OVERLAY_V131='/* DVSwitch-Mods: responsive column alignment and compact header v1.3.1 */ .nav #modeInfo > fieldset { margin-top:8px !important; } body:has(#dvs-asl-activity:not([hidden])) .nav #modeInfo > fieldset { margin-top:15px !important; } .header { padding:0; } .header h2 { margin:8px 0; } .container {'
CSS_LAYOUT_OVERLAY_V132='/* DVSwitch-Mods: responsive column alignment and compact header v1.3.2 */ .nav #modeInfo > fieldset { margin-top:1px !important; } body:has(#dvs-asl-activity:not([hidden])) .nav #modeInfo > fieldset { margin-top:15px !important; } body:has(#dvs-asl-activity:not([hidden])) .nav #modeInfo > span:first-child { position:relative; top:6px; } body:has(#dvs-asl-activity:not([hidden])) #dvs-asl-activity > span { position:relative; top:6px; } .header { padding:0; } .header h2 { margin:8px 0; } .container {'
CSS_LAYOUT_OVERLAY_V133='/* DVSwitch-Mods: responsive column alignment and compact header v1.3.3 */ .nav #modeInfo > fieldset { margin-top:8px !important; } body:has(#dvs-asl-activity:not([hidden])) .nav #modeInfo > fieldset { margin-top:15px !important; } body:has(#dvs-asl-activity:not([hidden])) .nav #modeInfo > span:first-child { position:relative; top:4px; } .header { padding:0; } .header h2 { margin:8px 0; } .container {'
CSS_LAYOUT_OVERLAY='/* DVSwitch-Mods: responsive column alignment and compact header v1.3.4 */ .nav #modeInfo > fieldset { margin-top:8px !important; } body:has(#dvs-asl-activity:not([hidden])) .nav #modeInfo > fieldset { margin-top:15px !important; } .nav #modeInfo > span:first-child { position:relative; top:-1px; } body:has(#dvs-asl-activity:not([hidden])) .nav #modeInfo > span:first-child { position:relative; top:4px; } body:has(#dvs-asl-activity:not([hidden])) #dvs-asl-activity { position:relative; top:-1px; } .header { padding:0; } .header h2 { margin:8px 0; } .container {'

log(){ echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }
die(){ log "ERROR: $*"; exit 1; }

need_root(){
  if [ "$(id -u)" -ne 0 ]; then
    die "Run with sudo."
  fi
}

require_file(){
  [ -f "$1" ] || die "Missing required file: $1"
}

copy_dashboard_files_to(){
  dest="$1"
  mkdir -p "$dest" || die "Could not create backup directory: $dest"

  cp -a "$INDEX_FILE" "$dest/index.php" || die "Could not backup index.php"
  cp -a "$CSS_FILE" "$dest/css.php" || die "Could not backup css.php"
  cp -a "$LH_FILE" "$dest/lh.php" || die "Could not backup lh.php"
  cp -a "$LOCALTX_FILE" "$dest/localtx.php" || die "Could not backup localtx.php"
  cp -a "$SYSTEM_FILE" "$dest/system.php" || die "Could not backup system.php"
}

restore_dashboard_files_from(){
  src="$1"

  [ -f "$src/index.php" ] || die "Backup missing index.php"
  [ -f "$src/css.php" ] || die "Backup missing css.php"
  [ -f "$src/lh.php" ] || die "Backup missing lh.php"
  [ -f "$src/localtx.php" ] || die "Backup missing localtx.php"
  [ -f "$src/system.php" ] || die "Backup missing system.php"

  cp -a "$src/index.php" "$INDEX_FILE" || die "Could not restore index.php"
  cp -a "$src/css.php" "$CSS_FILE" || die "Could not restore css.php"
  cp -a "$src/lh.php" "$LH_FILE" || die "Could not restore lh.php"
  cp -a "$src/localtx.php" "$LOCALTX_FILE" || die "Could not restore localtx.php"
  cp -a "$src/system.php" "$SYSTEM_FILE" || die "Could not restore system.php"
}

ensure_original_backup(){
  if [ -d "$ORIGINAL_BACKUP_DIR" ]; then
    log "Protected original backup already exists and will NOT be overwritten: $ORIGINAL_BACKUP_DIR"
    return 0
  fi

  log "Creating protected original dashboard backup: $ORIGINAL_BACKUP_DIR"
  copy_dashboard_files_to "$ORIGINAL_BACKUP_DIR"

  {
    echo "DVSwitch Dashboard Display Layout original backup"
    echo "Created: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "Script version: $VERSION"
    echo "This directory is intentionally preserved and should not be overwritten by later apply runs."
  } > "$ORIGINAL_BACKUP_DIR/README.txt" || true
}

create_run_backup(){
  log "Creating per-run backup: $RUN_BACKUP_DIR"
  copy_dashboard_files_to "$RUN_BACKUP_DIR"
}

replace_or_confirm(){
  file="$1"
  old="$2"
  new="$3"
  label="$4"

  if grep -Fq "$old" "$file"; then
    sed -i "s|$old|$new|g" "$file" || die "Failed changing: $label"
    log "Changed: $label"
  elif grep -Fq "$new" "$file"; then
    log "Already applied: $label"
  else
    log "WARNING: Expected string not found for: $label"
    log "WARNING: File may be newer, customized, or already changed differently: $file"
  fi
}

# Replace a literal CSS block so punctuation in selectors is not interpreted by sed.
replace_exact_or_confirm(){
  file="$1" old="$2" new="$3" label="$4"
  python3 - "$file" "$old" "$new" "$label" <<'PY_LAYOUT_EXACT_REPLACE' || die "Failed changing: $label"
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text(encoding='utf-8')
old, new, label = sys.argv[2:5]
if text.count(old) == 1:
    path.write_text(text.replace(old, new, 1), encoding='utf-8')
    print(f"Changed: {label}")
elif new in text:
    print(f"Already applied: {label}")
else:
    print(f"WARNING: Expected supported CSS block not found for: {label}")
    raise SystemExit(1)
PY_LAYOUT_EXACT_REPLACE
}

# Upgrade stock and previously capped widths to the current viewport-based sizes.
replace_layout_variants(){
  file="$1"
  new="$2"
  label="$3"
  shift 3
  changed=0

  while [ "$#" -gt 0 ]; do
    old="$1"
    shift
    if grep -Fq "$old" "$file"; then
      sed -i "s|$old|$new|g" "$file" || die "Failed changing: $label"
      changed=1
    fi
  done

  if [ "$changed" -eq 1 ]; then
    log "Changed: $label"
  elif grep -Fq "$new" "$file"; then
    log "Already applied: $label"
  else
    log "WARNING: Expected original or supported previous width not found for: $label"
    log "WARNING: File may be newer, customized, or already changed differently: $file"
  fi
}

apply_responsive(){
  need_root

  require_file "$INDEX_FILE"
  require_file "$CSS_FILE"
  require_file "$LH_FILE"
  require_file "$LOCALTX_FILE"
  require_file "$SYSTEM_FILE"

  ensure_original_backup
  create_run_backup

  log "Applying DVSwitch Dashboard display layout tweaks v$VERSION"

  # Let the two-column dashboard table divide the viewport instead of adding 100% beside the fixed status column.
  replace_or_confirm "$INDEX_FILE" 'style="border:none; border-collapse:collapse; cellspacing:0; cellpadding:0; background-color:#fafafa;"' 'style="border:none; border-collapse:collapse; cellspacing:0; cellpadding:0; background-color:#fafafa; width:100%; table-layout:fixed;"' "index.php main content table fills available width"
  replace_or_confirm "$INDEX_FILE" '<td valign="top" style="border:none; height: 480px; background-color:#fafafa; width:100%;">' '<td valign="top" style="border:none; height: 480px; background-color:#fafafa;">' "index.php content column no longer forces overflow"

  # Let the dashboard and its main panels use the available browser viewport width.
  replace_layout_variants "$CSS_FILE" "width: 96vw;" "css.php fluid dashboard width" "width: 900px;" "width: min(96vw, 1200px);"
  log "Preserved stock nav width: width : 185px; (no responsive nav-width patch applied)"
  replace_or_confirm "$CSS_FILE" "white-space: nowrap;" "white-space: normal;" "css.php table white-space nowrap -> normal"
  # Preserve prior overlays during upgrades so the owned CSS remains reversible.
  if grep -Fq 'DVSwitch-Mods: responsive column alignment and compact header v1.3.4' "$CSS_FILE"; then
    log "Already applied: responsive column alignment and compact header"
  elif grep -Fq 'DVSwitch-Mods: responsive column alignment and compact header v1.3.3' "$CSS_FILE"; then
    replace_exact_or_confirm "$CSS_FILE" "$CSS_LAYOUT_OVERLAY_V133" "$CSS_LAYOUT_OVERLAY" "css.php one-pixel heading and ASL panel alignment"
  elif grep -Fq 'DVSwitch-Mods: responsive column alignment and compact header v1.3.2' "$CSS_FILE"; then
    replace_exact_or_confirm "$CSS_FILE" "$CSS_LAYOUT_OVERLAY_V132" "$CSS_LAYOUT_OVERLAY" "css.php measured card and heading alignment"
  elif grep -Fq 'DVSwitch-Mods: responsive column alignment and compact header v1.3.1' "$CSS_FILE"; then
    replace_exact_or_confirm "$CSS_FILE" "$CSS_LAYOUT_OVERLAY_V131" "$CSS_LAYOUT_OVERLAY" "css.php guide spacing and panel alignment"
  elif grep -Fq 'DVSwitch-Mods: responsive column alignment and compact header v1.3.0' "$CSS_FILE"; then
    replace_exact_or_confirm "$CSS_FILE" "$CSS_LAYOUT_OVERLAY_V130" "$CSS_LAYOUT_OVERLAY" "css.php mode-aware status alignment and compact header"
  else
    replace_exact_or_confirm "$CSS_FILE" '.container {' "$CSS_LAYOUT_OVERLAY" "css.php mode-aware status alignment and compact header"
  fi

  replace_layout_variants "$LH_FILE" "width:95%;" "lh.php Gateway Activity fluid width" "width:640px;" "width:min(95%,1400px);"
  replace_layout_variants "$LOCALTX_FILE" "width:95%;" "localtx.php Local Activity fluid width" "width:640px;" "width:min(95%,1400px);"

  replace_layout_variants "$SYSTEM_FILE" "width:95%" "system.php Hardware Info fluid width" "width:855px" "width:min(95%,1400px)"
  replace_or_confirm "$SYSTEM_FILE" "margin-left:6px;margin-right:0px" "margin-left:auto;margin-right:auto" "system.php Hardware Info margin center"

  log "Responsive dashboard tweaks complete."
  log "Protected original backup: $ORIGINAL_BACKUP_DIR"
  log "Per-run backup: $RUN_BACKUP_DIR"
  log "Refresh the DVSwitch Dashboard in the browser."
  log "Log file: $LOG_FILE"
}

restore_latest_run_backup(){
  need_root

  latest="$(find "$ROOT" -maxdepth 1 -type d -name '.dvs-dashboard-display-backup-*' | sort | tail -n 1)"
  [ -n "$latest" ] || die "No per-run display dashboard backup directory found in $ROOT"

  restore_dashboard_files_from "$latest"

  log "Restored dashboard files from latest per-run backup: $latest"
  log "Protected original backup was not changed: $ORIGINAL_BACKUP_DIR"
  log "Log file: $LOG_FILE"
}

restore_original_backup(){
  need_root

  [ -d "$ORIGINAL_BACKUP_DIR" ] || die "Protected original backup does not exist: $ORIGINAL_BACKUP_DIR"

  restore_dashboard_files_from "$ORIGINAL_BACKUP_DIR"

  log "Restored dashboard files from protected original backup: $ORIGINAL_BACKUP_DIR"
  log "This should return the dashboard files to their pre-display-patch state."
  log "Log file: $LOG_FILE"
}

show_status(){
  echo "DVSwitch Dashboard Display Layout v$VERSION"
  echo
  echo "Tracked files:"
  echo "  $INDEX_FILE"
  echo "  $CSS_FILE"
  echo "  $LH_FILE"
  echo "  $LOCALTX_FILE"
  echo "  $SYSTEM_FILE"
  echo
  if [ -d "$ORIGINAL_BACKUP_DIR" ]; then
    echo "Protected original backup: FOUND"
    echo "  $ORIGINAL_BACKUP_DIR"
  else
    echo "Protected original backup: NOT FOUND"
  fi
  echo
  echo "Current responsive markers:"
  grep -Hn 'width:100%;\|width: 96vw;\|white-space: normal;\|width:95%;\|margin-left:auto;margin-right:auto' "$INDEX_FILE" "$CSS_FILE" "$LH_FILE" "$LOCALTX_FILE" "$SYSTEM_FILE" 2>/dev/null || true
}

case "${1:-menu}" in
  check|--check)
    need_root
    require_file "$INDEX_FILE"
    require_file "$CSS_FILE"
    require_file "$LH_FILE"
    require_file "$LOCALTX_FILE"
    require_file "$SYSTEM_FILE"
    [ ! -L "$INDEX_FILE" ] && [ ! -L "$CSS_FILE" ] && [ ! -L "$LH_FILE" ] && [ ! -L "$LOCALTX_FILE" ] && [ ! -L "$SYSTEM_FILE" ] || die "Refusing symlink dashboard target."
    printf '%s\n' "PASS: all five dashboard files required by the display-layout mod are present."
    ;;
  apply)
    apply_responsive
    ;;
  restore-latest)
    restore_latest_run_backup
    ;;
  restore-original|restore-factory)
    restore_original_backup
    ;;
  status)
    show_status
    ;;
  *)
    echo "DVSwitch Dashboard Display Layout v$VERSION"
    echo "1 = Apply dispaly layout tweaks"
    echo "2 = Restore latest per-run backup"
    echo "3 = Restore protected original files"
    echo "4 = Show display-layout status markers"
    echo "0 = Exit"
    printf "Choose an action [0/1/2/3/4]: "
    read -r choice
    case "$choice" in
      1) apply_responsive ;;
      2) restore_latest_run_backup ;;
      3) restore_original_backup ;;
      4) show_status ;;
      0) exit 0 ;;
      *) die "Invalid choice" ;;
    esac
    ;;
esac
