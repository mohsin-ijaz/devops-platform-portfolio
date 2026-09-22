const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const supportsFinePointer = window.matchMedia("(hover: hover) and (pointer: fine)");

function setupNavigation() {
  const toggle = document.querySelector(".nav-toggle");
  const links = document.querySelector("#nav-links");

  if (!toggle || !links) return;

  const closeNavigation = () => {
    links.classList.remove("is-open");
    toggle.setAttribute("aria-expanded", "false");
  };

  toggle.addEventListener("click", () => {
    const isOpen = links.classList.toggle("is-open");
    toggle.setAttribute("aria-expanded", String(isOpen));
  });

  links.addEventListener("click", (event) => {
    if (event.target instanceof HTMLAnchorElement) closeNavigation();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeNavigation();
  });
}

function setupReveal() {
  const items = document.querySelectorAll(".reveal");
  const groups = document.querySelectorAll(
    ".metric-grid, .project-grid, .stack-grid, .sre-grid, .automation-list, .principles-grid, .repo-grid"
  );

  groups.forEach((group) => {
    group.querySelectorAll(":scope > .reveal").forEach((item, index) => {
      item.style.setProperty("--reveal-delay", `${Math.min(index * 75, 300)}ms`);
    });
  });

  if (prefersReducedMotion.matches || !("IntersectionObserver" in window)) {
    items.forEach((item) => item.classList.add("is-visible"));
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      });
    },
    { threshold: 0.12, rootMargin: "0px 0px -7%" }
  );

  items.forEach((item) => observer.observe(item));
}

function setupCounters() {
  const counters = document.querySelectorAll("[data-count]");

  const render = (element, value) => {
    const prefix = element.dataset.prefix || "";
    const suffix = element.dataset.suffix || "";
    element.textContent = `${prefix}${value}${suffix}`;
  };

  const runCounter = (element) => {
    const target = Number(element.dataset.count || "0");
    const duration = 1250;
    const start = performance.now();

    const tick = (now) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 4);
      render(element, Math.round(target * eased));
      if (progress < 1) requestAnimationFrame(tick);
    };

    requestAnimationFrame(tick);
  };

  if (prefersReducedMotion.matches || !("IntersectionObserver" in window)) return;

  counters.forEach((counter) => render(counter, 0));

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        runCounter(entry.target);
        observer.unobserve(entry.target);
      });
    },
    { threshold: 0.55 }
  );

  counters.forEach((counter) => observer.observe(counter));
}

function setupTerminal() {
  const line = document.querySelector("[data-terminal-line]");
  if (!line || prefersReducedMotion.matches) return;

  const commands = [
    "terraform plan -var-file environments/prod.tfvars",
    "kubectl diff -k infrastructure/kustomize/kafka/overlays/prod",
    "helm upgrade --atomic --timeout 10m platform-service ./helm",
    "mimirtool rules sync mimir-rules-finops.yaml",
    "python train.py --config config/features.yaml",
    "gcloud sql backups list --filter type=ON_DEMAND"
  ];

  let commandIndex = 0;
  let charIndex = commands[0].length;
  let deleting = true;

  const typeNext = () => {
    const command = commands[commandIndex];

    if (deleting) {
      charIndex -= 2;
      if (charIndex <= 0) {
        charIndex = 0;
        deleting = false;
        commandIndex = (commandIndex + 1) % commands.length;
      }
    } else {
      charIndex += 1;
      if (charIndex >= commands[commandIndex].length) {
        charIndex = commands[commandIndex].length;
        deleting = true;
        line.textContent = commands[commandIndex];
        window.setTimeout(typeNext, 2100);
        return;
      }
    }

    line.textContent = commands[commandIndex].slice(0, charIndex);
    window.setTimeout(typeNext, deleting ? 24 : 42);
  };

  window.setTimeout(typeNext, 1900);
}

function setupScrollState() {
  const progress = document.querySelector(".scroll-progress span");
  const header = document.querySelector(".site-header");
  let ticking = false;

  const update = () => {
    const scrollRange = document.documentElement.scrollHeight - window.innerHeight;
    const ratio = scrollRange > 0 ? Math.min(window.scrollY / scrollRange, 1) : 0;
    if (progress) progress.style.transform = `scaleX(${ratio})`;
    if (header) header.classList.toggle("is-scrolled", window.scrollY > 18);
    ticking = false;
  };

  window.addEventListener(
    "scroll",
    () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(update);
    },
    { passive: true }
  );

  update();
}

function setupActiveNavigation() {
  if (!("IntersectionObserver" in window)) return;

  const links = Array.from(document.querySelectorAll('.nav-links a[href^="#"]'));
  const sections = links
    .map((link) => document.querySelector(link.getAttribute("href")))
    .filter(Boolean);

  const observer = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];

      if (!visible) return;
      links.forEach((link) => {
        const active = link.getAttribute("href") === `#${visible.target.id}`;
        link.classList.toggle("is-active", active);
        if (active) link.setAttribute("aria-current", "location");
        else link.removeAttribute("aria-current");
      });
    },
    { rootMargin: "-28% 0px -58%", threshold: [0.05, 0.2, 0.5] }
  );

  sections.forEach((section) => observer.observe(section));
}

function setupTilt() {
  if (prefersReducedMotion.matches || !supportsFinePointer.matches) return;

  const cards = document.querySelectorAll(".metric-card, .project-card, .repo-link, .terminal-card");

  cards.forEach((card) => {
    let frame = 0;

    card.addEventListener("pointermove", (event) => {
      if (frame) cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const bounds = card.getBoundingClientRect();
        const x = (event.clientX - bounds.left) / bounds.width - 0.5;
        const y = (event.clientY - bounds.top) / bounds.height - 0.5;
        const strength = card.classList.contains("terminal-card") ? 2.2 : 1.5;
        card.style.setProperty("--tilt-x", `${(-y * strength).toFixed(2)}deg`);
        card.style.setProperty("--tilt-y", `${(x * strength).toFixed(2)}deg`);
      });
    });

    card.addEventListener("pointerleave", () => {
      card.style.setProperty("--tilt-x", "0deg");
      card.style.setProperty("--tilt-y", "0deg");
    });
  });
}

function setupNetworkCanvas() {
  const canvas = document.querySelector("#network-canvas");
  if (!(canvas instanceof HTMLCanvasElement) || prefersReducedMotion.matches) return;

  const context = canvas.getContext("2d");
  if (!context) return;

  const nodes = [];
  const pointer = { x: -9999, y: -9999 };
  const colors = ["125, 211, 252", "110, 231, 183", "251, 191, 36"];
  let lastFrame = 0;
  let animationFrame = 0;

  function resize() {
    const pixelRatio = Math.min(window.devicePixelRatio || 1, 1.5);
    canvas.width = Math.floor(window.innerWidth * pixelRatio);
    canvas.height = Math.floor(window.innerHeight * pixelRatio);
    canvas.style.width = `${window.innerWidth}px`;
    canvas.style.height = `${window.innerHeight}px`;
    context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
  }

  function createNodes() {
    const nodeCount = Math.min(68, Math.max(30, Math.floor(window.innerWidth / 24)));
    nodes.length = 0;
    for (let index = 0; index < nodeCount; index += 1) {
      nodes.push({
        x: Math.random() * window.innerWidth,
        y: Math.random() * window.innerHeight,
        vx: (Math.random() - 0.5) * 0.16,
        vy: (Math.random() - 0.5) * 0.16,
        radius: Math.random() * 1.35 + 0.75,
        color: colors[index % colors.length]
      });
    }
  }

  function drawConnection(a, b, distance, maxDistance, time, signal) {
    const opacity = Math.max(0, 1 - distance / maxDistance) * 0.22;
    context.strokeStyle = `rgba(125, 211, 252, ${opacity})`;
    context.lineWidth = 0.75;
    context.beginPath();
    context.moveTo(a.x, a.y);
    context.lineTo(b.x, b.y);
    context.stroke();

    if (!signal) return;
    const travel = (time / 8500 + signal * 0.09) % 1;
    const x = a.x + (b.x - a.x) * travel;
    const y = a.y + (b.y - a.y) * travel;
    context.fillStyle = `rgba(110, 231, 183, ${Math.min(opacity * 3.4, 0.72)})`;
    context.beginPath();
    context.arc(x, y, 1.25, 0, Math.PI * 2);
    context.fill();
  }

  function draw(time) {
    animationFrame = requestAnimationFrame(draw);
    if (document.hidden || time - lastFrame < 32) return;
    lastFrame = time;

    context.clearRect(0, 0, window.innerWidth, window.innerHeight);
    const maxDistance = window.innerWidth < 700 ? 88 : 128;

    for (let index = 0; index < nodes.length; index += 1) {
      const node = nodes[index];
      node.x += node.vx;
      node.y += node.vy;

      if (node.x < -10 || node.x > window.innerWidth + 10) node.vx *= -1;
      if (node.y < -10 || node.y > window.innerHeight + 10) node.vy *= -1;

      const pointerDistance = Math.hypot(node.x - pointer.x, node.y - pointer.y);
      if (pointerDistance < 145) {
        node.x += (node.x - pointer.x) * 0.0012;
        node.y += (node.y - pointer.y) * 0.0012;
      }

      for (let otherIndex = index + 1; otherIndex < nodes.length; otherIndex += 1) {
        const other = nodes[otherIndex];
        const distance = Math.hypot(node.x - other.x, node.y - other.y);
        if (distance < maxDistance) {
          const signal = (index + otherIndex) % 19 === 0 ? index + otherIndex : 0;
          drawConnection(node, other, distance, maxDistance, time, signal);
        }
      }

      context.fillStyle = `rgba(${node.color}, 0.54)`;
      context.beginPath();
      context.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
      context.fill();
    }
  }

  let resizeTimer = 0;
  window.addEventListener("resize", () => {
    window.clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(() => {
      resize();
      createNodes();
    }, 120);
  });

  window.addEventListener("pointermove", (event) => {
    pointer.x = event.clientX;
    pointer.y = event.clientY;
  });

  window.addEventListener("pointerleave", () => {
    pointer.x = -9999;
    pointer.y = -9999;
  });

  window.addEventListener("pagehide", () => cancelAnimationFrame(animationFrame), { once: true });

  resize();
  createNodes();
  animationFrame = requestAnimationFrame(draw);
}

setupNavigation();
setupReveal();
setupCounters();
setupTerminal();
setupScrollState();
setupActiveNavigation();
setupTilt();
setupNetworkCanvas();
