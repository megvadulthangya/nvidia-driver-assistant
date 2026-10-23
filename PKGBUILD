# Maintainer: Gyöngyösi Gábor <gabor at gshoots dot hu>

pkgname=nvidia-driver-assistant
pkgver=0.62.71.09_1.g356838eb8e
pkgrel=1
pkgdesc="Detect and install the best NVIDIA driver packages for the system (Manjaro-only fork)"
arch=('any')
url="https://github.com/megvadulthangya/nvidia-driver-assistant"
license=('MIT' 'custom')
depends=('python' 'python-pyyaml')
makedepends=('git' 'curl' 'libarchive' 'gzip')

# Source code comes from the Manjaro-only git branch.  The DEB is pulled
# in prepare() only for the production supported-gpus.json and NVIDIA EULA.
# supportedchips.html is downloaded from the latest New Feature Branch and
# used as the authoritative GPU -> branch source (overrides the JSON when
# NVIDIA manipulates the legacybranch field).
source=(
  "git+https://github.com/megvadulthangya/nvidia-driver-assistant.git#branch=manjaro"
  "show-driver"
)
sha256sums=(
  'SKIP'
  'SKIP'
)

_nvidia_repo_base='https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64'
_nvidia_unix_page='https://www.nvidia.com/en-us/drivers/unix/'
_nvidia_chips_base='https://us.download.nvidia.com/XFree86/Linux-x86_64'

_latest_deb_info() {
  local html latest_file ver
  html=$(curl -fsSL --retry 3 --retry-delay 2 --connect-timeout 10 "${_nvidia_repo_base}/") || return 1
  latest_file=$(echo "$html" | grep -oP 'nvidia-driver-assistant_[\d\.-]+_all\.deb' | sort -V | tail -n1)

  if [[ -z "$latest_file" ]]; then
    return 1
  fi

  ver=$(echo "$latest_file" | sed -E 's/nvidia-driver-assistant_(.*)_all\.deb/\1/')
  echo "${ver}|${latest_file}"
}

_latest_nfb_version() {
  local html ver
  html=$(curl -fsSL --retry 3 --retry-delay 2 --connect-timeout 10 \
    -A "Mozilla/5.0 (X11; Linux x86_64)" "${_nvidia_unix_page}") || return 1
  ver=$(echo "$html" | grep -oP 'Latest New Feature Branch Version:\s*\K[0-9.]+' | head -n1)
  [[ -n "$ver" ]] && echo "$ver"
}

pkgver() {
  cd "${srcdir}/${pkgname}"

  local meta deb_ver git_hash
  meta="$(_latest_deb_info)" || return 1

  deb_ver="${meta%%|*}"
  deb_ver="${deb_ver//-/_}"
  git_hash="$(git rev-parse --short=10 HEAD)"

  printf '%s.g%s' "${deb_ver}" "${git_hash}"
}

prepare() {
  cd "${srcdir}"

  # 1. Download and unpack upstream DEB (supported-gpus.json + EULA)
  local meta deb_file deb_url
  meta="$(_latest_deb_info)" || return 1
  deb_file="${meta#*|}"
  deb_url="${_nvidia_repo_base}/${deb_file}"

  rm -rf "debroot"
  mkdir -p "debroot"

  echo "==> Downloading upstream DEB for assets: ${deb_file}..."
  curl -fL --retry 5 -o "upstream.deb" "${deb_url}"

  echo "==> Unpacking DEB payload..."
  bsdtar -xf "upstream.deb" -C "debroot"

  local data_tar
  data_tar=$(find "debroot" -maxdepth 1 -type f \( -name 'data.tar.*' -o -name 'data.tar' \) | head -n1)

  if [[ -n "$data_tar" ]]; then
    bsdtar -xf "$data_tar" -C "debroot"
    rm "$data_tar"
  fi

  # 2. Download supportedchips.html from the latest New Feature Branch.
  #    This is the authoritative GPU -> branch table used by the parser
  #    to override the JSON when NVIDIA manipulates the legacybranch field.
  echo "==> Determining latest New Feature Branch version..."
  local nfb_version
  nfb_version="$(_latest_nfb_version)" || true

  if [[ -z "$nfb_version" ]]; then
    error "Could not determine latest New Feature Branch version from ${_nvidia_unix_page}"
    return 1
  fi

  echo "==> Latest New Feature Branch: ${nfb_version}"
  local chips_url="${_nvidia_chips_base}/${nfb_version}/README/supportedchips.html"
  echo "==> Downloading supportedchips.html: ${chips_url}"
  rm -f "supportedchips.html"
  curl -fL --retry 5 -o "supportedchips.html" "${chips_url}"
}

package() {
  # 1. Directory structure
  install -d "${pkgdir}/usr/bin"
  install -d "${pkgdir}/usr/share/${pkgname}"
  install -d "${pkgdir}/usr/share/doc/${pkgname}"
  install -d "${pkgdir}/usr/share/licenses/${pkgname}"

  # Determine Python site-packages path
  local site_packages
  site_packages="$(python -c 'import site; print(site.getsitepackages()[0])')"
  install -d "${pkgdir}${site_packages}/nvidia_driver_assistant/data"

  # 2. Main wrapper script from git -> /usr/bin/
  msg2 "Installing main script from git source..."
  install -m755 "${srcdir}/${pkgname}/nvidia-driver-assistant" \
    "${pkgdir}/usr/bin/nvidia-driver-assistant"

  # 3. Python package from git -> site-packages (modules + YAML data)
  msg2 "Installing Python package (nvidia_driver_assistant/)..."
  install -m644 "${srcdir}/${pkgname}/nvidia_driver_assistant/"*.py \
    "${pkgdir}${site_packages}/nvidia_driver_assistant/"
  install -m644 "${srcdir}/${pkgname}/nvidia_driver_assistant/data/"*.yaml \
    "${pkgdir}${site_packages}/nvidia_driver_assistant/data/"

  # 3.5 supportedchips.html -> package data directory
  if [[ -f "${srcdir}/supportedchips.html" ]]; then
    msg2 "Installing supportedchips.html..."
    install -m644 "${srcdir}/supportedchips.html" \
      "${pkgdir}${site_packages}/nvidia_driver_assistant/data/supportedchips.html"
  else
    error "supportedchips.html is missing from prepare()"
    return 1
  fi

  # 4. show-driver wrapper (declared in source=)
  if [[ -f "${srcdir}/show-driver" ]]; then
    msg2 "Installing show-driver as nvidia-recommended-driver..."
    install -m755 "${srcdir}/show-driver" \
      "${pkgdir}/usr/bin/nvidia-recommended-driver"
  else
    error "show-driver is missing from srcdir"
    return 1
  fi

  # 5. Data files from DEB (production supported-gpus.json, icons, etc.)
  if [[ -d "${srcdir}/debroot/usr/share/${pkgname}" ]]; then
    cp -ra "${srcdir}/debroot/usr/share/${pkgname}"/* "${pkgdir}/usr/share/${pkgname}/"
  fi

  # 6. Documentation from git
  install -m644 "${srcdir}/${pkgname}/README.md" \
    "${pkgdir}/usr/share/doc/${pkgname}/README.md"
  install -m644 "${srcdir}/${pkgname}/docs/Configuration.md" \
    "${pkgdir}/usr/share/doc/${pkgname}/Configuration.md"
  install -m644 "${srcdir}/${pkgname}/COPYING" \
    "${pkgdir}/usr/share/licenses/${pkgname}/COPYING"

  # 7. Licenses from DEB (copyright + NVIDIA EULA)
  local deb_doc="${srcdir}/debroot/usr/share/doc/${pkgname}"
  if [[ -f "${deb_doc}/copyright" ]]; then
    install -m644 "${deb_doc}/copyright" "${pkgdir}/usr/share/licenses/${pkgname}/copyright"
  fi

  local eula="${srcdir}/debroot/usr/share/${pkgname}/driver_eula/LICENSE"
  if [[ -f "$eula" ]]; then
    install -m644 "$eula" "${pkgdir}/usr/share/licenses/${pkgname}/NVIDIA-EULA"
  fi
}