# Maintainer: Philip Müller <philm[at]manjaro[dot]org>
# Contributor: Alberto Milone <amilone@nvidia.com>

pkgbase=nvidia-driver-assistant
pkgname=('nvidia-driver-assistant')
pkgver=0.9.57.01
pkgrel=2
_pkgrel=1
arch=('any')
url="http://www.nvidia.com/"
license=('MIT')
options=('!strip')
source=(https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/"$pkgbase"_"$pkgver"-"$_pkgrel"_all.deb
        show-driver manjaro.patch)
sha256sums=('267186285e3c5fb6e76924ddd5f199cc5a7c14646bbdca95eff186ff055a20c8'
            'ba2de9ef5a7295b3127bef360a5da89cacaec7c7362e351b33177045bcf9e3f7'
            '37a6c0708ffebc63f22b2bd2d0ca0f04172e6b39968e867b783f132168f42e8c')

package_nvidia-driver-assistant() {
  pkgdesc="Detect and install the best NVIDIA driver packages for the system. This piece of software is meant to help users deciding on which NVIDIA graphics driver to install, based on the detected system's hardware."
  arch=('any')
  depends=('python')

  # Extract package data
  bsdtar -xvf data.tar.xz -C "${pkgdir}/"
  
  cd "${pkgdir}"
  patch -p1 -i ${srcdir}/manjaro.patch

  # Cleanup
  rm "${pkgdir}"/usr/share/doc/nvidia-driver-assistant/changelog.Debian.gz
  
  install -m755 "${srcdir}/show-driver" "${pkgdir}/usr/bin/nvidia-recommended-driver"
}
