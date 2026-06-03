#!/usr/bin/env node
/**
 * Self-contained OpenAI image generator.
 *
 * Reads OPENAI_API_KEY from (in order): process env → <skill>/.env → ./.env
 * Picks the model automatically: --transparent ⇒ gpt-image-1, else gpt-image-2.
 * Override anytime with --model. Retries transient errors (429/5xx) with backoff.
 *
 * Usage:
 *   node scripts/generate.mjs --prompt "a tropical palm leaf" [options]
 *
 * Options:
 *   --prompt <text>     Required. The image prompt.
 *   --out <path>        Output file (default: ./openai-image-<timestamp>.png).
 *   --model <name>      Force a model (gpt-image-1 | gpt-image-2). Default: auto.
 *   --size <WxH>        Image size (default: 1024x1024). Also 1536x1024, 1024x1536, auto.
 *   --quality <level>   low | medium | high | auto (default: high).
 *   --transparent       Transparent background (forces gpt-image-1).
 *   --n <count>         Number of images (default: 1). >1 appends -1, -2, … to --out.
 *   --dry-run           Print resolved config + prompt, no API call.
 */

import { mkdir, writeFile, readFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, resolve, join, extname } from "node:path";
import { fileURLToPath } from "node:url";
import { argv, env, exit } from "node:process";

const API_URL = "https://api.openai.com/v1/images/generations";
const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const SKILL_DIR = resolve(SCRIPT_DIR, "..");

// --- arg parsing -----------------------------------------------------------

function parseArgs(args) {
  const out = {};
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (!a.startsWith("--")) continue;
    const key = a.slice(2);
    const next = args[i + 1];
    if (next === undefined || next.startsWith("--")) {
      out[key] = true;
    } else {
      out[key] = next;
      i++;
    }
  }
  return out;
}

const args = parseArgs(argv.slice(2));

const prompt = typeof args.prompt === "string" ? args.prompt : null;
const transparent = Boolean(args.transparent);
const size = typeof args.size === "string" ? args.size : "1024x1024";
const quality = typeof args.quality === "string" ? args.quality : "high";
const count = Math.max(1, parseInt(args.n, 10) || 1);
const dryRun = Boolean(args["dry-run"]);

// Auto model selection: transparency only exists on gpt-image-1.
const model =
  typeof args.model === "string"
    ? args.model
    : transparent
      ? "gpt-image-1"
      : "gpt-image-2";

const defaultOut = `./openai-image-${Date.now()}.png`;
const outPath = typeof args.out === "string" ? args.out : defaultOut;

// --- validation ------------------------------------------------------------

if (!prompt) {
  console.error('Missing --prompt "…"');
  exit(1);
}

if (transparent && model !== "gpt-image-1") {
  console.error(
    `Transparent backgrounds require gpt-image-1, but --model ${model} was given.\n` +
      `Drop --model (auto-selects gpt-image-1) or set --model gpt-image-1.`,
  );
  exit(1);
}

// --- API key resolution -----------------------------------------------------

function parseEnvFile(text) {
  const result = {};
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq === -1) continue;
    const key = trimmed.slice(0, eq).trim();
    let val = trimmed.slice(eq + 1).trim();
    if (
      (val.startsWith('"') && val.endsWith('"')) ||
      (val.startsWith("'") && val.endsWith("'"))
    ) {
      val = val.slice(1, -1);
    }
    result[key] = val;
  }
  return result;
}

async function resolveApiKey() {
  if (env.OPENAI_API_KEY) return env.OPENAI_API_KEY;
  for (const candidate of [join(SKILL_DIR, ".env"), resolve(process.cwd(), ".env")]) {
    if (existsSync(candidate)) {
      const parsed = parseEnvFile(await readFile(candidate, "utf8"));
      if (parsed.OPENAI_API_KEY) return parsed.OPENAI_API_KEY;
    }
  }
  return null;
}

// --- dry run ----------------------------------------------------------------

if (dryRun) {
  console.log("=== DRY RUN — no API call ===");
  console.log(`model:       ${model}${args.model ? "" : " (auto)"}`);
  console.log(`size:        ${size}`);
  console.log(`quality:     ${quality}`);
  console.log(`transparent: ${transparent}`);
  console.log(`count:       ${count}`);
  console.log(`out:         ${outPath}`);
  console.log(`\nprompt:\n${prompt}`);
  exit(0);
}

// --- generate ---------------------------------------------------------------

const apiKey = await resolveApiKey();
if (!apiKey) {
  console.error(
    "Missing OPENAI_API_KEY.\n" +
      `Add it to ${join(SKILL_DIR, ".env")} (OPENAI_API_KEY=sk-…) or export it in your shell.`,
  );
  exit(1);
}

const body = { model, prompt, size, quality, n: count };
if (transparent) body.background = "transparent";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function callApi(maxAttempts = 4) {
  let lastErr;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    let res;
    try {
      res = await fetch(API_URL, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });
    } catch (err) {
      // Network-level failure — retry.
      lastErr = err;
      if (attempt < maxAttempts) {
        const wait = 1000 * 2 ** (attempt - 1);
        console.warn(`Network error (${err.message}); retrying in ${wait / 1000}s…`);
        await sleep(wait);
        continue;
      }
      throw err;
    }

    if (res.ok) return res.json();

    const text = await res.text();
    // 429 / 5xx are transient — back off and retry. 4xx (except 429) is fatal.
    if ((res.status === 429 || res.status >= 500) && attempt < maxAttempts) {
      const wait = 1000 * 2 ** (attempt - 1);
      console.warn(`API ${res.status}; retrying in ${wait / 1000}s…`);
      await sleep(wait);
      lastErr = new Error(`API ${res.status}: ${text}`);
      continue;
    }
    console.error(`OpenAI API error ${res.status}: ${text}`);
    exit(1);
  }
  throw lastErr ?? new Error("Unknown API failure");
}

console.log(
  `Requesting ${model} (${size}, quality=${quality}${transparent ? ", transparent" : ""}${count > 1 ? `, n=${count}` : ""})…`,
);

let json;
try {
  json = await callApi();
} catch (err) {
  console.error(err.message ?? err);
  exit(1);
}

const images = Array.isArray(json?.data) ? json.data : [];
if (images.length === 0 || !images[0].b64_json) {
  console.error(`Unexpected response shape: ${JSON.stringify(json).slice(0, 500)}`);
  exit(1);
}

// --- write ------------------------------------------------------------------

const ext = extname(outPath) || ".png";
const base = outPath.slice(0, outPath.length - ext.length);

for (let i = 0; i < images.length; i++) {
  const b64 = images[i].b64_json;
  if (!b64) continue;
  const target = images.length === 1 ? outPath : `${base}-${i + 1}${ext}`;
  const abs = resolve(target);
  await mkdir(dirname(abs), { recursive: true });
  const buf = Buffer.from(b64, "base64");
  await writeFile(abs, buf);
  console.log(`Saved ${target} (${(buf.byteLength / 1024).toFixed(1)} KB)`);
}

if (json.usage) console.log("Usage:", JSON.stringify(json.usage));
