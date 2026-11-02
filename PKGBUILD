# Maintainer: DerNoli

pkgname=imac_fancontrol
pkgver=2.0
pkgrel=3
pkgdesc="Mac Fan Tray + Fan Daemon for Linux for 7.3 kernel"
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

# macfan und macfan-tray.py sind neu (Min 1200 / Max 4000, FORCE_MAX).
# Für die übrigen Dateien: 'updpkgsums' ausführen.
sha256sums=('7048c52b71a0662171a18ad02f663b7e2f33d42283c00e3506d042c347cebdae'
            'SKIP'
            '3e007601c592fd6c3d89b7af9fe3b41d119faf4e62bc272714274a5d85c0c4af'
            'SKIP'
            'SKIP')

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
