# Maintainer: Philip Müller <philm[at]manjaro[dot]org>

pkgname=nvidia-driver-assistant
pkgver=0.18.86.15
pkgrel=1
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
sha256sums=('ededbfd205985346b9f69ed986893be9ee818d0c54e9d6da6eb9677639cbc2ff'
            'ba2de9ef5a7295b3127bef360a5da89cacaec7c7362e351b33177045bcf9e3f7'
            '6cd1a0f543d72a3f87a32786b97d4de907d596c038eaf53abb8415bf5054daa4')

package() {

  # Extract package data
  bsdtar -xvf data.tar.xz -C "${pkgdir}/"
  
  cd "${pkgdir}"
  patch -p1 -i "${srcdir}/manjaro.patch"

  # Cleanup
  rm "${pkgdir}"/usr/share/doc/nvidia-driver-assistant/changelog.Debian.gz
  
  install -m755 "${srcdir}/show-driver" "${pkgdir}/usr/bin/nvidia-recommended-driver"
}
