"use client";

import { useEffect } from "react";

function trackHeroPointer(hero: HTMLElement) {
  const motion = window.matchMedia("(hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference)");
  let frame: number | undefined;
  let pointerX = 0;
  let pointerY = 0;

  const update = () => {
    frame = undefined;
    const { left, top, width, height } = hero.getBoundingClientRect();
    hero.style.setProperty("--hero-parallax-x", `${((pointerX - left) / width - .5) * 30}px`);
    hero.style.setProperty("--hero-parallax-y", `${((pointerY - top) / height - .5) * 22}px`);
  };

  const move = (event: PointerEvent) => {
    if (!motion.matches || event.pointerType !== "mouse") return;
    pointerX = event.clientX;
    pointerY = event.clientY;
    if (frame === undefined) frame = requestAnimationFrame(update);
  };

  const reset = () => {
    if (frame !== undefined) cancelAnimationFrame(frame);
    frame = undefined;
    hero.style.removeProperty("--hero-parallax-x");
    hero.style.removeProperty("--hero-parallax-y");
  };

  hero.addEventListener("pointermove", move, { passive: true });
  hero.addEventListener("pointerleave", reset);
  motion.addEventListener("change", reset);

  return () => {
    hero.removeEventListener("pointermove", move);
    hero.removeEventListener("pointerleave", reset);
    motion.removeEventListener("change", reset);
    reset();
  };
}

export function LandingMotion() {
  useEffect(() => {
    const landing = document.getElementById("tillfold-landing");
    if (!landing) return;

    const reveals = typeof IntersectionObserver === "undefined" ? null : new IntersectionObserver((entries) => {
      for (const { target, isIntersecting } of entries) {
        if (!isIntersecting) continue;
        target.setAttribute("data-landing-entered", "");
        reveals?.unobserve(target);
      }
    }, { rootMargin: "0px 0px 8% 0px" });

    landing.querySelectorAll("[data-landing-reveal]").forEach((element) => reveals?.observe(element));

    const header = landing.querySelector<HTMLElement>("[data-landing-header]");
    const nav = header?.querySelector("nav");
    if (!header || !nav) return () => reveals?.disconnect();

    const hero = landing.querySelector<HTMLElement>("[data-landing-hero]");
    const stopTrackingHero = hero && trackHeroPointer(hero);

    const links = Array.from(nav.querySelectorAll<HTMLAnchorElement>('a[href^="#"]'));
    const sections = links.map((link) => ({ link, section: document.getElementById(link.hash.slice(1)) })).reverse();
    let activeLink: HTMLAnchorElement | undefined;
    let frame: number | undefined;

    const update = () => {
      frame = undefined;
      header.toggleAttribute("data-landing-scrolled", window.scrollY > 12);
      const readingLine = header.getBoundingClientRect().bottom + 30;
      const atBottom = window.scrollY > 0 && landing.getBoundingClientRect().bottom <= window.innerHeight + 2;
      const nextLink = atBottom ? sections[0]?.link :
        sections.find(({ section }) => section && section.getBoundingClientRect().top <= readingLine)?.link;

      if (activeLink !== nextLink) {
        activeLink?.removeAttribute("aria-current");
        nextLink?.setAttribute("aria-current", "location");
        activeLink = nextLink;
      }

      nav.toggleAttribute("data-landing-current", Boolean(activeLink));
      if (activeLink) {
        nav.style.setProperty("--landing-tab-x", `${activeLink.offsetLeft}px`);
        nav.style.setProperty("--landing-tab-width", `${activeLink.offsetWidth}px`);
      }
    };

    const schedule = () => {
      if (frame === undefined) frame = requestAnimationFrame(update);
    };

    const resize = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(schedule);
    resize?.observe(header);
    resize?.observe(landing);
    links.forEach((link) => resize?.observe(link));
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    update();

    return () => {
      if (frame !== undefined) cancelAnimationFrame(frame);
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      stopTrackingHero?.();
      resize?.disconnect();
      reveals?.disconnect();
    };
  }, []);

  return null;
}
