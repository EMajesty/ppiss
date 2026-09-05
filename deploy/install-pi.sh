#!/bin/sh
set -eu

REPO=${PPISS_REPO:-https://github.com/EMajesty/ppiss.git}
REF=${PPISS_REF:-main}
INSTALL_DIR=/opt/ppiss
BOOT_DIR=/boot/firmware
VIDEO_MODE=${PPISS_VIDEO_MODE:-HDMI-A-1:1280x800M@60,rotate=90}

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this installer as root (pipe it to sudo sh)." >&2
  exit 1
fi
if [ ! -f /etc/os-release ] || ! grep -q 'Raspberry Pi OS\|Raspbian' /etc/os-release; then
  echo "This installer supports Raspberry Pi OS only." >&2
  exit 1
fi
if [ ! -d "$BOOT_DIR" ]; then BOOT_DIR=/boot; fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends fonts-dejavu-core git python3-pygame python3-setuptools python3-venv python3-wheel

getent group render >/dev/null 2>&1 || groupadd --system render
id ppiss >/dev/null 2>&1 || useradd --system --home-dir "$INSTALL_DIR" --shell /usr/sbin/nologin ppiss
usermod -a -G video,render ppiss

if [ -d "$INSTALL_DIR/.git" ]; then
  runuser -u ppiss -- git -C "$INSTALL_DIR" fetch origin "$REF"
  runuser -u ppiss -- git -C "$INSTALL_DIR" checkout "$REF"
  runuser -u ppiss -- git -C "$INSTALL_DIR" pull --ff-only origin "$REF"
elif [ -e "$INSTALL_DIR" ]; then
  echo "$INSTALL_DIR exists but is not a Git checkout; refusing to overwrite it." >&2
  exit 1
else
  git clone --branch "$REF" --depth 1 "$REPO" "$INSTALL_DIR"
  chown -R ppiss:ppiss "$INSTALL_DIR"
fi

python3 -m venv --system-site-packages "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install --no-build-isolation --no-deps "$INSTALL_DIR"
chown -R ppiss:ppiss "$INSTALL_DIR/.venv"
install -m 0644 "$INSTALL_DIR/deploy/ppiss.service" /etc/systemd/system/ppiss.service
install -m 0644 "$INSTALL_DIR/deploy/10-usb0.network" /etc/systemd/network/10-usb0.network

CONFIG_FILE="$BOOT_DIR/config.txt"
CMDLINE_FILE="$BOOT_DIR/cmdline.txt"
grep -qxF 'dtoverlay=dwc2' "$CONFIG_FILE" || printf '\ndtoverlay=dwc2\n' >> "$CONFIG_FILE"
append_cmdline() {
  case " $(cat "$CMDLINE_FILE") " in *" $1 "*) ;; *) sed -i "1 s|$| $1|" "$CMDLINE_FILE" ;; esac
}
append_cmdline 'modules-load=dwc2,g_ether'
append_cmdline 'consoleblank=0'
append_cmdline 'vt.global_cursor_default=0'
append_cmdline 'loglevel=3'
if [ -n "$VIDEO_MODE" ]; then append_cmdline "video=$VIDEO_MODE"; fi

mkdir -p /etc/NetworkManager/conf.d
cat > /etc/NetworkManager/conf.d/90-ppiss-usb0.conf <<'EOF'
[keyfile]
unmanaged-devices=interface-name:usb0
EOF
systemctl enable systemd-networkd.service
systemctl disable getty@tty1.service >/dev/null 2>&1 || true
systemctl daemon-reload
systemctl enable ppiss.service

echo "PPISS installation complete. Run 'sudo reboot' to activate it."
echo "The Pi will use 10.55.0.2 on usb0 and listen on UDP port 45891."
