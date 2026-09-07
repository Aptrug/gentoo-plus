EAPI=8

DESCRIPTION="Private, fast, and honest web browser based on Chromium"
HOMEPAGE="https://helium.computer/"

MY_P="helium-${PV}"
MY_D="${MY_P}-x86_64_linux"
MY_F="${MY_D}.tar.xz"

SRC_URI="https://github.com/imputnet/helium-linux/releases/download/${PV}/${MY_F}"

S=${WORKDIR}

LICENSE="GPL-3 BSD"
SLOT="0"
KEYWORDS="amd64"
RESTRICT="mirror bindist strip"

RDEPEND="
	app-accessibility/at-spi2-core
	dev-libs/nspr
	dev-libs/nss
	net-print/cups
	x11-libs/cairo
	x11-libs/libXcomposite
	x11-libs/libXdamage
	x11-libs/libxkbcommon
	x11-libs/pango
"

QA_PREBUILT="*"

src_unpack() {
	:
}

src_install() {
	dodir /opt/helium
	cd "${ED}/opt/helium" || die
	unpack "${MY_F}"
	mv "${MY_D}"/* . || die
	rm -rf "${MY_D}" || die
	# find . \( -name "*.so" -o -name "*.so.*" \) -type f -delete || die
	find locales -type f ! -name "en-US.pak" -delete || die
	# rm -f chrome helium.desktop product_logo_256.png apparmor.cfg \
	# 	chromedriver helium-wrapper
	rm -f chromedriver
	printf '#!/bin/bash\nfor f in /tmp/dbus-??????????; do [[ -S $f ]] && DBUS_SESSION_BUS_ADDRESS="unix:path=$f" exec /opt/helium/helium --no-sandbox "$@"; done\n' > "${T}/helium" || die
	dobin "${T}/helium"
}
