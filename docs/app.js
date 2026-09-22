const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

function setupNavigation() {
  const toggle = document.querySelector(".nav-toggle");
  const links = document.querySelector("#nav-links");

  if (!toggle || !links) return;

  toggle.addEventListener("click", () => {
    const isOpen = links.classList.toggle("is-open");
    toggle.setAttribute("aria-expanded", String(isOpen));
  });

  links.addEventListener("click", (event) => {
    if (event.target instanceof HTMLAnchorElement) {
      links.classList.remove("is-open");
      toggle.setAttribute("aria-expanded", "false");
    }
  });
}

function setupReveal() {
  const items = document.querySelectorAll(".reveal");

  if (prefersReducedMotion.matches || !("IntersectionObserver" in window)) {
    items.forEach((item) => item.classList.add("is-visible"));
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.15 }
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
    const duration = prefersReducedMotion.matches ? 0 : 1100;
    const start = performance.now();

    const tick = (now) => {
      const progress = duration === 0 ? 1 : Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      render(element, Math.round(target * eased));

      if (progress < 1) {
        requestAnimationFrame(tick);
      }
    };

    requestAnimationFrame(tick);
  };

  if (prefersReducedMotion.matches || !("IntersectionObserver" in window)) {
    counters.forEach((counter) => runCounter(counter));
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          runCounter(entry.target);
          observer.unobserve(entry.target);
        }
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

  window.setInterval(() => {
    const command = commands[commandIndex];

    if (deleting) {
      charIndex -= 2;
      if (charIndex <= 0) {
        deleting = false;
        commandIndex = (commandIndex + 1) % commands.length;
      }
    } else {
      charIndex += 2;
      if (charIndex >= commands[commandIndex].length) {
        deleting = true;
      }
    }

    line.textContent = commands[commandIndex].slice(0, Math.max(charIndex, 0));
  }, 74);
}

function setupNetworkCanvas() {
  const canvas = document.querySelector("#network-canvas");
  if (!(canvas instanceof HTMLCanvasElement) || prefersReducedMotion.matches) return;

  const context = canvas.getContext("2d");
  if (!context) return;

  const nodes = [];
  const nodeCount = Math.min(72, Math.max(34, Math.floor(window.innerWidth / 22)));
  const pointer = { x: -9999, y: -9999 };

  function resize() {
    const pixelRatio = window.devicePixelRatio || 1;
    canvas.width = Math.floor(window.innerWidth * pixelRatio);
    canvas.height = Math.floor(window.innerHeight * pixelRatio);
    canvas.style.width = `${window.innerWidth}px`;
    canvas.style.height = `${window.innerHeight}px`;
    context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
  }

  function createNodes() {
    nodes.length = 0;
    for (let i = 0; i < nodeCount; i += 1) {
      nodes.push({
        x: Math.random() * window.innerWidth,
        y: Math.random() * window.innerHeight,
        vx: (Math.random() - 0.5) * 0.22,
        vy: (Math.random() - 0.5) * 0.22,
        radius: Math.random() * 1.7 + 1.1
      });
    }
  }

  function drawLine(a, b, distance, maxDistance) {
    const opacity = Math.max(0, 1 - distance / maxDistance) * 0.33;
    context.strokeStyle = `rgba(103, 232, 249, ${opacity})`;
    context.lineWidth = 1;
    context.beginPath();
    context.moveTo(a.x, a.y);
    context.lineTo(b.x, b.y);
    context.stroke();
  }

  function draw() {
    context.clearRect(0, 0, window.innerWidth, window.innerHeight);

    const maxDistance = window.innerWidth < 700 ? 92 : 132;

    for (let i = 0; i < nodes.length; i += 1) {
      const node = nodes[i];
      node.x += node.vx;
      node.y += node.vy;

      if (node.x < 0 || node.x > window.innerWidth) node.vx *= -1;
      if (node.y < 0 || node.y > window.innerHeight) node.vy *= -1;

      const pointerDistance = Math.hypot(node.x - pointer.x, node.y - pointer.y);
      if (pointerDistance < 130) {
        node.x += (node.x - pointer.x) * 0.002;
        node.y += (node.y - pointer.y) * 0.002;
      }

      for (let j = i + 1; j < nodes.length; j += 1) {
        const other = nodes[j];
        const distance = Math.hypot(node.x - other.x, node.y - other.y);
        if (distance < maxDistance) drawLine(node, other, distance, maxDistance);
      }

      context.fillStyle = "rgba(238, 247, 255, 0.58)";
      context.beginPath();
      context.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
      context.fill();
    }

    requestAnimationFrame(draw);
  }

  window.addEventListener("resize", () => {
    resize();
    createNodes();
  });

  window.addEventListener("pointermove", (event) => {
    pointer.x = event.clientX;
    pointer.y = event.clientY;
  });

  window.addEventListener("pointerleave", () => {
    pointer.x = -9999;
    pointer.y = -9999;
  });

  resize();
  createNodes();
  draw();
}

setupNavigation();
setupReveal();
setupCounters();
setupTerminal();
setupNetworkCanvas();
