EAPI=8

DESCRIPTION="Linux LTS kernel sources"
HOMEPAGE="https://www.kernel.org"
SRC_URI="https://cdn.kernel.org/pub/linux/kernel/v${PV%%.*}.x/linux-${PV}.tar.xz"

S="${WORKDIR}/linux-${PV}"
LICENSE="GPL-2"
SLOT="${PV}"
KEYWORDS="amd64"

src_compile() { :; }

src_install() {
	dodir "/usr/src/linux-${PV}"
	cp -a "${S}/." "${ED}/usr/src/linux-${PV}/"
}

pkg_postinst() {
	ln -sfn "linux-${PV}" "${EROOT}/usr/src/linux"
}

pkg_postrm() {
	rm -rf "${EROOT}/usr/src/linux-${PV}"
}
