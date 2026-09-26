EAPI=8

DESCRIPTION="The web browser from Google"
HOMEPAGE="https://www.google.com/chrome/"

MY_PN="${PN}-stable"
MY_P="${MY_PN}_${PV}-1"
MY_F="${MY_P}_amd64.deb"

SRC_URI="https://dl.google.com/linux/chrome/deb/pool/main/g/${MY_PN}/${MY_F}"

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
	dodir /opt/google/chrome
	cd "${WORKDIR}" || die
	ar x "${DISTDIR}/${MY_F}" data.tar.xz || die
	tar xf data.tar.xz ./opt/google/chrome || die
	rm data.tar.xz || die
	cp -a opt/google/chrome/. "${ED}/opt/google/chrome/" || die
	cd "${ED}/opt/google/chrome" || die
	# find . \( -name "*.so" -o -name "*.so.*" \) -type f -delete || die
	find locales -type f ! -name "en-US.pak" -delete || die
	# rm -f google-chrome chrome-management-service \
	      # CHROME_VERSION_EXTRA default-app-block \
	      # product_logo_*.png
	# rm -rf MEIPreload PrivacySandboxAttestationsPreloaded \
	       # cron default_apps
	rm -f chromedriver
	printf '#!/bin/bash\nfor f in /tmp/dbus-??????????; do [[ -S $f ]] && DBUS_SESSION_BUS_ADDRESS="unix:path=$f" exec /opt/google/chrome/chrome --no-sandbox "$@"; done\n' > "${T}/chrome" || die
	dobin "${T}/chrome"
}
