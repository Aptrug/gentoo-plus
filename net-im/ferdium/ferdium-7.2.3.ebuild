EAPI=8

DESCRIPTION="All-in-one messaging app combining your chat and workspace services"
HOMEPAGE="https://ferdium.org/"

MY_D="Ferdium-linux-${PV}"
MY_F="${MY_D}.tar.gz"

SRC_URI="https://github.com/ferdium/ferdium-app/releases/download/v${PV}/${MY_F}"

S=${WORKDIR}

LICENSE="Apache-2.0 MIT BSD"
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
	dodir /opt/ferdium
	cd "${ED}/opt/ferdium" || die
	unpack "${MY_F}"
	mv "${MY_D}"/* . || die
	rm -rf "${MY_D}" || die
	find locales -type f ! -name "en-US.pak" -delete || die
	printf '#!/bin/bash\nfor f in /tmp/dbus-??????????; do [[ -S $f ]] && DBUS_SESSION_BUS_ADDRESS="unix:path=$f" exec /opt/ferdium/ferdium --no-sandbox "$@"; done\n' > "${T}/ferdium" || die
	dobin "${T}/ferdium"
}
