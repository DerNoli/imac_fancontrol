# Maintainer: DerNoli

pkgname=imac_fancontrol
pkgver=1.5
pkgrel=2
pkgdesc="Mac Fan Tray + Fan Daemon for Linux"
arch=('any')
url="https://example.com"
license=('MIT')
depends=('python' 'python-pyqt6' 'bc' 'lm_sensors' 'breeze-icons')
install="${pkgname}.install"

# If these files are in the same folder as the PKGBUILD, 
# keep them as listed. Otherwise, use full URLs.
source=(
    'macfan'
    'macfan.service'
    'macfan-tray.py'
    'macfantray.desktop'
    'macfantray.service'
)

# Use 'updpkgsums' to generate these properly before uploading
sha256sums=('SKIP' 'SKIP' 'SKIP' 'SKIP' 'SKIP')

package() {
    # Install system-level fan script
    install -Dm755 "${srcdir}/macfan" \
        "${pkgdir}/usr/bin/macfan"

    # Install tray Python application (renamed to executable)
    install -Dm755 "${srcdir}/macfan-tray.py" \
        "${pkgdir}/usr/bin/macfantray"

    # Install desktop launcher
    install -Dm644 "${srcdir}/macfantray.desktop" \
        "${pkgdir}/usr/share/applications/macfantray.desktop"

    # Install systemd system service (fan daemon)
    install -Dm644 "${srcdir}/macfan.service" \
        "${pkgdir}/usr/lib/systemd/system/macfan.service"

    # Install systemd user service (tray icon)
    install -Dm644 "${srcdir}/macfantray.service" \
        "${pkgdir}/usr/lib/systemd/user/macfantray.service"
}
