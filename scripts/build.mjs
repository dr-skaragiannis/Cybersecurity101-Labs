#!/usr/bin/env node
/**
 * Compiles the Markdown lab guides in content/guides/{en,el} into the static
 * site in docs/, which GitHub Pages serves from the main branch (/docs).
 *
 * Usage: npm run build
 */
import { marked } from "marked";
import { mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const contentDir = path.join(root, "content", "guides");
const outDir = path.join(root, "docs");

const SITE_NAME = "Cybersecurity101-Labs";

const LANGS = [
  {
    code: "en",
    htmlLang: "en",
    label: "English",
    other: "el",
    otherLabel: "Ελληνικά",
    strings: {
      index: "Index",
      previous: "Previous",
      next: "Next",
      start: "Start the learning path",
      disclaimer:
        "Educational use only — practise these techniques only against machines you own or are explicitly authorised to test.",
      built: "Built from Markdown with marked",
    },
  },
  {
    code: "el",
    htmlLang: "el",
    label: "Ελληνικά",
    other: "en",
    otherLabel: "English",
    strings: {
      index: "Ευρετήριο",
      previous: "Προηγούμενο",
      next: "Επόμενο",
      start: "Ξεκινήστε τη διαδρομή μάθησης",
      disclaimer:
        "Μόνο για εκπαιδευτική χρήση — εφαρμόστε αυτές τις τεχνικές μόνο σε μηχανές που σας ανήκουν ή για τις οποίες έχετε ρητή άδεια δοκιμής.",
      built: "Μετατράπηκε από Markdown με το marked",
    },
  },
];

marked.setOptions({ gfm: true });

/* ---------------------------------------------------------------- helpers */

const escapeHtml = (s) =>
  s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

/** GitHub-style heading slug (keeps unicode letters, e.g. Greek). */
function slugify(text) {
  return text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\-_\s]/gu, "")
    .trim()
    .replace(/\s/g, "-");
}

/** Give every heading a unique id so in-page TOC links work. */
function addHeadingIds(html) {
  const seen = new Map();
  return html.replace(/<h([1-6])([^>]*)>([\s\S]*?)<\/h\1>/g, (m, depth, attrs, inner) => {
    if (/\sid=/.test(attrs)) return m;
    const slug = slugify(inner.replace(/<[^>]+>/g, ""));
    if (!slug) return m;
    const count = seen.get(slug) ?? 0;
    seen.set(slug, count + 1);
    const id = count === 0 ? slug : `${slug}-${count}`;
    return `<h${depth}${attrs} id="${id}">${inner}</h${depth}>`;
  });
}

/** Rewrite relative .md links to their generated .html counterparts. */
function rewriteLinks(md) {
  return md.replace(/\]\(([^)\s]+)\)/g, (match, target) => {
    if (/^[a-z][a-z0-9+.-]*:/i.test(target) || target.startsWith("#")) return match;
    const hashAt = target.indexOf("#");
    const filePart = hashAt === -1 ? target : target.slice(0, hashAt);
    const hash = hashAt === -1 ? "" : target.slice(hashAt);
    if (!filePart.endsWith(".md")) return match;
    const base = path.posix.basename(filePart);
    const dir = path.posix.dirname(filePart);
    const htmlFile = base === "README.md" ? "index.html" : base.replace(/\.md$/, ".html");
    const newFile = (dir === "." ? "" : `${dir}/`) + htmlFile;
    return `](${newFile}${hash})`;
  });
}

const firstHeading = (md) => {
  const m = /^#\s+(.+)$/m.exec(md);
  return m ? m[1].trim() : null;
};

/* ----------------------------------------------------------------- pages */

function document({ lang, prefix, title, description, body, headExtra = "" }) {
  return `<!doctype html>
<html lang="${lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(title)}</title>
<meta name="description" content="${escapeHtml(description)}">
<meta name="generator" content="cybersecurity101-labs build script">
<link rel="stylesheet" href="${prefix}assets/style.css">
${headExtra}</head>
<body>
${body}
</body>
</html>
`;
}

function siteHeader({ prefix, currentLang, langs }) {
  const links = langs
    .map((l) => {
      const cls = l.code === currentLang ? ' class="active"' : "";
      return `<a href="${prefix}${l.code}/index.html"${cls}>${l.label}</a>`;
    })
    .join("\n      ");
  return `<header class="site-header">
  <a class="brand" href="${prefix}index.html">Cybersecurity<span>101-Labs</span></a>
  <nav aria-label="Languages">
      ${links}
  </nav>
</header>`;
}

function siteFooter({ prefix, strings }) {
  return `<footer class="site-footer">
  <p class="disclaimer">⚠ ${escapeHtml(strings.disclaimer)}</p>
  <p>${escapeHtml(SITE_NAME)} · <a href="${prefix}index.html">${escapeHtml(strings.index)}</a> · ${escapeHtml(strings.built)} · <a href="https://github.com/dr-skaragiannis/Cybersecurity101-Labs/blob/main/LICENSE">MIT</a></p>
</footer>`;
}

/* ---------------------------------------------------------------- build */

async function build() {
  const theme = await readFile(path.join(root, "scripts", "theme.css"), "utf8");

  await rm(outDir, { recursive: true, force: true });
  await mkdir(path.join(outDir, "assets"), { recursive: true });
  await writeFile(path.join(outDir, "assets", "style.css"), theme, "utf8");
  await writeFile(path.join(outDir, ".nojekyll"), "", "utf8");

  const landingCards = [];

  for (const langCfg of LANGS) {
    const dir = path.join(contentDir, langCfg.code);
    const files = (await readdir(dir))
      .filter((f) => f.endsWith(".md"))
      .sort((a, b) => (a === "README.md" ? -1 : b === "README.md" ? 1 : a.localeCompare(b)));

    const entries = [];
    for (const file of files) {
      const md = await readFile(path.join(dir, file), "utf8");
      entries.push({
        file,
        out: file === "README.md" ? "index.html" : file.replace(/\.md$/, ".html"),
        title: firstHeading(md) ?? file.replace(/\.md$/, ""),
        html: addHeadingIds(marked.parse(rewriteLinks(md))),
        isIndex: file === "README.md",
        num: /^(\d+)-/.exec(file)?.[1] ?? null,
      });
    }

    const guides = entries.filter((e) => !e.isIndex);
    await mkdir(path.join(outDir, langCfg.code), { recursive: true });

    for (const entry of entries) {
      const idx = guides.indexOf(entry);
      const prev = idx > 0 ? guides[idx - 1] : null;
      const next = idx !== -1 && idx < guides.length - 1 ? guides[idx + 1] : null;
      const s = langCfg.strings;

      const pager =
        entry.isIndex
          ? `<nav class="pager pager-single"><a class="next" href="${guides[0].out}">${escapeHtml(s.start)} →</a></nav>`
          : `<nav class="pager">
  ${prev ? `<a class="prev" href="${prev.out}">← ${escapeHtml(s.previous)}: ${escapeHtml(prev.title)}</a>` : "<span></span>"}
  ${next ? `<a class="next" href="${next.out}">${escapeHtml(s.next)}: ${escapeHtml(next.title)} →</a>` : "<span></span>"}
</nav>`;

      const body = `${siteHeader({ prefix: "../", currentLang: langCfg.code, langs: LANGS })}
<main class="content">
  <div class="toolbar">
    <a class="crumb" href="index.html">← ${escapeHtml(s.index)}</a>
    <a class="lang-switch" href="../${langCfg.other}/${entry.out}" hreflang="${langCfg.other}">${langCfg.otherLabel}</a>
  </div>
  <article>
${entry.html}
  </article>
  ${pager}
</main>
${siteFooter({ prefix: "../", strings: s })}`;

      const page = document({
        lang: langCfg.htmlLang,
        prefix: "../",
        title: `${entry.title} — ${SITE_NAME}`,
        description: `${SITE_NAME}: ${langCfg.label} lab guide ${entry.num ?? ""} ${entry.title}`.trim(),
        body,
      });
      await writeFile(path.join(outDir, langCfg.code, entry.out), page, "utf8");
    }

    landingCards.push({ lang: langCfg, guides });
  }

  /* ------------------------------------------------------------ landing */

  const cards = landingCards
    .map(({ lang, guides }) => {
      const items = guides
        .map(
          (g) =>
            `<li><a href="${lang.code}/${g.out}"><span class="num">${g.num}</span><span class="t">${escapeHtml(g.title)}</span></a></li>`
        )
        .join("\n");
      return `<section class="card">
  <h2><a href="${lang.code}/index.html">${lang.label} <span class="arrow">→</span></a></h2>
  <ol class="guide-list">
${items}
  </ol>
</section>`;
    })
    .join("\n");

  const landingBody = `${siteHeader({ prefix: "", currentLang: null, langs: LANGS })}
<main class="content landing">
  <section class="hero">
    <h1>Cybersecurity<span>101-Labs</span></h1>
    <p class="tagline">Hands-on, open-source lab guides for learning offensive and defensive security in isolated environments.<br>
    Πρακτικοί, ανοικτοί εργαστηριακοί οδηγοί για εκμάθηση κυβερνοασφάλειας σε απομονωμένο περιβάλλον.</p>
    <p class="warning">⚠ <strong>Educational use only / Μόνο για εκπαιδευτική χρήση.</strong> Practise these techniques only against machines you own or are explicitly authorised to test.</p>
  </section>
  ${cards}
  <section class="card">
    <h2>Build it yourself</h2>
    <p>The site is plain HTML compiled from the Markdown guides in <code>content/guides</code>:</p>
    <pre><code>npm install
npm run build   <span class="c"># writes the site to docs/</span></code></pre>
    <p>Source, issues and contributions: <a href="https://github.com/dr-skaragiannis/Cybersecurity101-Labs">github.com/dr-skaragiannis/Cybersecurity101-Labs</a></p>
  </section>
</main>
${siteFooter({ prefix: "", strings: LANGS[0].strings })}`;

  await writeFile(
    path.join(outDir, "index.html"),
    document({
      lang: "en",
      prefix: "",
      title: `${SITE_NAME} — Hands-on cybersecurity lab guides`,
      description:
        "Hands-on, open-source cybersecurity lab guides (EN + ΕΛ) compiled to a static site: Linux fundamentals, SSH, file shares, firewalls, honeypots, packet capture and CTF walkthroughs.",
      body: landingBody,
    }),
    "utf8"
  );

  const pageCount = landingCards.reduce((n, c) => n + c.guides.length + 1, 0) + 1;
  console.log(`Built ${pageCount} pages into ${path.relative(process.cwd(), outDir)}/`);
}

build().catch((err) => {
  console.error(err);
  process.exit(1);
});
