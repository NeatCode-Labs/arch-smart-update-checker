# Maintainer: NeatCode Labs <contact@neatcodelabs.com>

pkgname=arch-smart-update-checker
pkgver=0.2.0
pkgrel=1
pkgdesc="Smart Arch update helper with news awareness"
arch=('any')
url="https://github.com/NeatCode-Labs/arch-smart-update-checker"
license=('MIT')
depends=('python' 'python-feedparser' 'python-colorama' 'pacman-contrib')
source=("$pkgname-$pkgver.tar.gz::https://github.com/NeatCode-Labs/arch-smart-update-checker/archive/refs/tags/v$pkgver.tar.gz")
sha256sums=('SKIP')

package() {
  cd "${srcdir}/${pkgname}-${pkgver}"
  install -Dm755 arch-smart-update-checker.py "${pkgdir}/usr/bin/asuc"
  install -Dm644 LICENSE "${pkgdir}/usr/share/licenses/${pkgname}/LICENSE"
  install -Dm644 README.md "${pkgdir}/usr/share/doc/${pkgname}/README.md"
} 