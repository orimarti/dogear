#!/usr/bin/env node
// Stand-in for `claude` and `codex` in the demo recording. It writes the same
// live-session file Claude Code does, so `dogear add` detects it for real, and
// treats "/dogear ARGS" the way the dogear skill does: by running `dogear add ARGS`.
"use strict";
const fs = require("fs");
const path = require("path");
const readline = require("readline");
const { spawnSync } = require("child_process");

const agent = path.basename(process.argv[1]);
const args = process.argv.slice(2);
const home = process.env.HOME;
const cwd = process.cwd();
const tilde = (p) => (p.startsWith(home) ? "~" + p.slice(home.length) : p);
const dim = (s) => `\x1b[2m${s}\x1b[0m`;
const accent = (s) => `\x1b[38;5;209m${s}\x1b[0m`;

const sessions = JSON.parse(fs.readFileSync(path.join(home, ".demo", "sessions.json"), "utf8"));
let id = agent === "claude" ? args[args.indexOf("--resume") + 1] : args[args.indexOf("resume") + 1];
const resumed = args.includes("--resume") || args.includes("resume");
if (!resumed) id = Object.keys(sessions).find((k) => sessions[k].cwd === cwd);
const title = (sessions[id] || {}).title || "new session";

let live = null;
if (agent === "claude") {
  live = path.join(home, ".claude", "sessions", `${process.pid}.json`);
  fs.mkdirSync(path.dirname(live), { recursive: true });
  fs.writeFileSync(live, JSON.stringify({ pid: process.pid, sessionId: id, cwd, status: "idle" }));
}

console.log(accent(`● ${agent}`) + dim(`  ${tilde(cwd)}  ·  ${resumed ? "resumed: " : ""}${title}`));
console.log();

const rl = readline.createInterface({ input: process.stdin, output: process.stdout, prompt: "> " });
const quit = () => {
  if (live) fs.rmSync(live, { force: true });
  process.exit(0);
};
rl.on("line", (line) => {
  line = line.trim();
  if (line === "/exit" || line === "exit") return quit();
  const m = line.match(/^[/$]dogear\s*(.*)$/);
  if (m) {
    const cmd = `dogear add ${m[1]}`.trim();
    console.log(accent("⏺ ") + `Bash(${cmd})`);
    const r = spawnSync("sh", ["-c", cmd], { encoding: "utf8" });
    for (const out of (r.stdout + r.stderr).trim().split("\n")) console.log(dim("  ⎿ ") + out);
    console.log();
  }
  rl.prompt();
});
rl.on("close", quit);
rl.prompt();
