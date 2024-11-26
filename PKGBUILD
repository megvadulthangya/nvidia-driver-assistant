# Maintainer: Philip Müller <philm[at]manjaro[dot]org>
# Contributor: Alberto Milone <amilone@nvidia.com>

pkgname=nvidia-driver-assistant
pkgver=0.9.57.01
pkgrel=3
_pkgrel=1
pkgdesc="Detect and install the best NVIDIA driver packages for the system"
arch=('any')
url="http://www.nvidia.com/"
license=('MIT')
depends=('python')
options=('!strip')
source=("https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/${pkgname}_${pkgver}-${_pkgrel}_all.deb"
        'show-driver'
        'manjaro.patch')
sha256sums=('267186285e3c5fb6e76924ddd5f199cc5a7c14646bbdca95eff186ff055a20c8'
            'ba2de9ef5a7295b3127bef360a5da89cacaec7c7362e351b33177045bcf9e3f7'
            '8b100e57c7789e0543e1ec4acb411856f6d067938e62f19dcbbb872cd2f76dad')

package() {

  # Extract package data
  bsdtar -xvf data.tar.xz -C "${pkgdir}/"
  
  cd "${pkgdir}"
  patch -p1 -i "${srcdir}/manjaro.patch"

  # Cleanup
  rm "${pkgdir}"/usr/share/doc/nvidia-driver-assistant/changelog.Debian.gz
  
  install -m755 "${srcdir}/show-driver" "${pkgdir}/usr/bin/nvidia-recommended-driver"
}
