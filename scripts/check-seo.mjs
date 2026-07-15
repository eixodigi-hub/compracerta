#!/usr/bin/env node
/**
 * Verificação automatizada de SEO para uma página publicada.
 *
 * Uso:
 *   node scripts/check-seo.mjs <url>
 *   node scripts/check-seo.mjs https://exemplo.com/imovel/123
 *
 * Analisa o HTML retornado e informa se estão presentes:
 *   - <title>
 *   - <meta name="description">
 *   - <link rel="canonical">
 *   - Dados estruturados JSON-LD (<script type="application/ld+json">)
 *
 * Saída: relatório legível + JSON. Exit code 0 se tudo OK, 1 se faltar algo.
 */

const url = process.argv[2];
if (!url) {
  console.error("Uso: node scripts/check-seo.mjs <url>");
  process.exit(2);
}

function extract(html, regex) {
  const m = html.match(regex);
  return m ? m[1].trim() : null;
}

function extractAll(html, regex) {
  const out = [];
  let m;
  while ((m = regex.exec(html)) !== null) out.push(m[1].trim());
  return out;
}

async function main() {
  let res;
  try {
    res = await fetch(url, {
      redirect: "follow",
      headers: { "User-Agent": "Lovable-SEO-Check/1.0" },
    });
  } catch (e) {
    console.error(`Falha ao buscar ${url}:`, e.message);
    process.exit(2);
  }

  if (!res.ok) {
    console.error(`HTTP ${res.status} ao buscar ${url}`);
    process.exit(2);
  }

  const html = await res.text();

  const title = extract(html, /<title[^>]*>([\s\S]*?)<\/title>/i);
  const description = extract(
    html,
    /<meta[^>]+name=["']description["'][^>]*content=["']([^"']*)["'][^>]*>/i,
  ) ?? extract(
    html,
    /<meta[^>]+content=["']([^"']*)["'][^>]+name=["']description["'][^>]*>/i,
  );
  const canonical = extract(
    html,
    /<link[^>]+rel=["']canonical["'][^>]*href=["']([^"']*)["'][^>]*>/i,
  ) ?? extract(
    html,
    /<link[^>]+href=["']([^"']*)["'][^>]+rel=["']canonical["'][^>]*>/i,
  );

  const jsonLdBlocks = extractAll(
    html,
    /<script[^>]+type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi,
  );

  const structured = [];
  const jsonLdErrors = [];
  for (const raw of jsonLdBlocks) {
    try {
      const parsed = JSON.parse(raw);
      const arr = Array.isArray(parsed) ? parsed : [parsed];
      for (const node of arr) {
        if (node && typeof node === "object") {
          structured.push(node["@type"] ?? "(sem @type)");
        }
      }
    } catch (e) {
      jsonLdErrors.push(e.message);
    }
  }

  const checks = {
    title: { present: !!title, value: title },
    description: { present: !!description, value: description },
    canonical: { present: !!canonical, value: canonical },
    structuredData: {
      present: structured.length > 0 && jsonLdErrors.length === 0,
      count: structured.length,
      types: structured,
      parseErrors: jsonLdErrors,
    },
  };

  const allOk =
    checks.title.present &&
    checks.description.present &&
    checks.canonical.present &&
    checks.structuredData.present;

  console.log(`\nSEO check: ${url}`);
  console.log("─".repeat(60));
  const mark = (ok) => (ok ? "✅" : "❌");
  console.log(`${mark(checks.title.present)} title        ${checks.title.value ?? "(ausente)"}`);
  console.log(`${mark(checks.description.present)} description  ${checks.description.value ?? "(ausente)"}`);
  console.log(`${mark(checks.canonical.present)} canonical    ${checks.canonical.value ?? "(ausente)"}`);
  console.log(
    `${mark(checks.structuredData.present)} JSON-LD      ${
      checks.structuredData.count
    } bloco(s)${
      checks.structuredData.types.length
        ? ` [${checks.structuredData.types.join(", ")}]`
        : ""
    }${
      jsonLdErrors.length ? ` — erros de parse: ${jsonLdErrors.length}` : ""
    }`,
  );
  console.log("─".repeat(60));
  console.log(JSON.stringify({ url, ok: allOk, checks }, null, 2));

  process.exit(allOk ? 0 : 1);
}

main();
