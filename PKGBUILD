# Maintainer: Philip Müller <philm[at]manjaro[dot]org>

pkgname=nvidia-driver-assistant
pkgver=0.22.82.07
pkgrel=1
_pkgrel=1
pkgdesc="Detect and install the best NVIDIA driver packages for the system"
arch=('any')
url="http://www.nvidia.com/"
license=('MIT AND LicenseRef-custom')
depends=('python')
source=("https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/${pkgname}_${pkgver}-${_pkgrel}_all.deb"
        'show-driver'
        'manjaro.patch')
sha256sums=('514294b8becbb0222a8fa7cb78bf1868935d5ecbe66e69baf073cea945684c8d'
            'ba2de9ef5a7295b3127bef360a5da89cacaec7c7362e351b33177045bcf9e3f7'
            '5b1c1416982628c1fc63df0f9ddf16e5ee93535c71cbb90d6e226b34fb38c0c2')

prepare() {
  mkdir -p "${pkgname}-${pkgver}"
  bsdtar -xvf data.tar.xz -C "${pkgname}-${pkgver}"

  cd "${pkgname}-${pkgver}"
  patch -Np1 -i "${srcdir}/manjaro.patch"
}

package() {
  cd "${pkgname}-${pkgver}"
  install -Dm755 "usr/bin/${pkgname}" -t "${pkgdir}/usr/bin/"
  install -Dm644 "usr/share/${pkgname}/supported-gpus"/*.json -t \
    "${pkgdir}/usr/share/${pkgname}/supported-gpus/"
  install -Dm644 "usr/share/doc/${pkgname}"/{CONTRIBUTING.md,README.md} -t \
    "$pkgdir/usr/share/doc/${pkgname}/"
  install -Dm644 "usr/share/doc/${pkgname}/copyright" -t \
    "$pkgdir/usr/share/licenses/${pkgname}/"
  install -Dm644 "usr/share/${pkgname}/driver_eula/LICENSE" -t \
    "${pkgdir}/usr/share/${pkgname}/driver_eula/"
  ln -s "/usr/share/${pkgname}/driver_eula/LICENSE" \
    "$pkgdir/usr/share/licenses/${pkgname}"
  install -m755 "${srcdir}/show-driver" "${pkgdir}/usr/bin/nvidia-recommended-driver"
}
