EAPI=8

DESCRIPTION="Fast, private and secure web browser based on Chromium"
HOMEPAGE="https://brave.com/"

MY_F="${P}-linux-amd64.zip"
SRC_URI="https://github.com/brave/brave-browser/releases/download/v${PV}/${MY_F}"

S=${WORKDIR}

LICENSE="MPL-2.0"
SLOT="0"
KEYWORDS="amd64"
RESTRICT="mirror bindist strip"

BDEPEND="app-arch/unzip"

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
	dodir /opt/brave.com/brave
	cd "${ED}/opt/brave.com/brave" || die
	unpack "${MY_F}"
	#  find . \( -name "*.so" -o -name "*.so.*" \) -type f -delete || die
	find locales -type f ! -name "en-US.pak" -delete || die
	# rm -f brave-browser chrome-management-service \
	# 	cron LICENSE default-app-block \
	# 	product_logo_*.png
	rm -f chromedriver
	printf '#!/bin/bash\nfor f in /tmp/dbus-??????????; do [[ -S $f ]] && DBUS_SESSION_BUS_ADDRESS="unix:path=$f" exec /opt/brave.com/brave/brave --no-sandbox "$@"; done\n' > "${T}/brave" || die
	dobin "${T}/brave"
}
