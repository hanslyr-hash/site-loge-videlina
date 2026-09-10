document.addEventListener("DOMContentLoaded", function () {

    const menuToggle = document.querySelector(".menu-toggle");
    const nav = document.querySelector("nav");
    const dropdown = document.querySelector(".nav-dropdown");
    const dropdownToggle = document.querySelector(".nav-dropdown-toggle");

    /* =========================================
       MENU MOBILE
       ========================================= */

    if (menuToggle && nav) {

        menuToggle.addEventListener("click", function () {

            nav.classList.toggle("open");

        });

    }


    /* =========================================
       DROPDOWN ACTIVITÉS
       ========================================= */

    if (dropdown && dropdownToggle) {

        dropdownToggle.addEventListener("click", function (event) {

            if (window.innerWidth <= 760) {

                event.preventDefault();

                dropdown.classList.toggle("mobile-open");

            }

        });

    }


    /* =========================================
       LIENS DU SOUS-MENU
       ========================================= */

    if (dropdown) {

        const submenuLinks =
            dropdown.querySelectorAll(".nav-dropdown-menu a");

        submenuLinks.forEach(function (link) {

            link.addEventListener("click", function () {

                if (window.innerWidth <= 760) {

                    dropdown.classList.remove("mobile-open");

                    if (nav) {
                        nav.classList.remove("open");
                    }

                }

            });

        });

    }


    /* =========================================
       AUTRES LIENS DU MENU MOBILE
       ========================================= */

    if (nav) {

        const links = nav.querySelectorAll("a");

        links.forEach(function (link) {

            if (
                dropdown &&
                dropdown.contains(link)
            ) {
                return;
            }

            link.addEventListener("click", function () {

                if (window.innerWidth <= 760) {

                    nav.classList.remove("open");

                    if (dropdown) {
                        dropdown.classList.remove("mobile-open");
                    }

                }

            });

        });

    }

});