const express = require("express");
const path    = require("path");
const app     = express();

app.use(express.json());

// Required for getUserMedia (camera) and WebAuthn to work.
// Browsers enforce these APIs only on secure contexts (HTTPS or localhost).
// These headers enable the SharedArrayBuffer API and tighten origin isolation —
// harmless on localhost, required if you ever deploy behind a reverse proxy.
app.use((req, res, next) => {
  res.setHeader("Cross-Origin-Opener-Policy",   "same-origin");
  res.setHeader("Cross-Origin-Embedder-Policy", "require-corp");
  next();
});

app.use(express.static(path.join(__dirname, "public")));

app.get("*", (req, res) => {
  res.sendFile(path.join(__dirname, "public", "index.html"));
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () =>
  console.log(`CRIDA Frontend running at http://localhost:${PORT}`)
);