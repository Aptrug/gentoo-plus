EAPI=8

DESCRIPTION="Timezone data"
HOMEPAGE="https://www.iana.org/time-zones"
SRC_URI="https://data.iana.org/time-zones/releases/tzdb-${PV}.tar.lz"
S="${WORKDIR}/tzdb-${PV}"

LICENSE="public-domain"
SLOT="0"
KEYWORDS="amd64"

src_compile() {
	emake zic
}

src_unpack() {
	bsdtar xf "${DISTDIR}/${A}"
}

src_install() {
	local zones=(africa antarctica asia australasia europe northamerica southamerica etcetera backward factory)
	./zic -b fat -d "${ED}/usr/share/zoneinfo" "${zones[@]}"
	insinto /usr/share/zoneinfo
	doins iso3166.tab zone1970.tab zone.tab leap-seconds.list
}
