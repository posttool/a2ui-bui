# a2ui.bundle.js (third-party)

`a2ui.bundle.js` is an unmodified esbuild bundle of the published
`@a2ui/web_core` and `@a2ui/lit` 0.14.0 npm packages and their runtime
dependencies. None of this code is written by this project. The full license
text of every bundled package is in [`LICENSE`](LICENSE).

| Package | Version | License | Source |
|---|---|---|---|
| `@a2ui/web_core` | 0.14.0 | Apache-2.0 | git+https://github.com/a2ui-project/a2ui.git |
| `@a2ui/lit` | 0.14.0 | Apache-2.0 | git+https://github.com/a2ui-project/a2ui.git |
| `lit` | 3.3.3 | BSD-3-Clause | git+https://github.com/lit/lit.git |
| `lit-html` | 3.3.0 | BSD-3-Clause | git+https://github.com/lit/lit.git |
| `lit-element` | 4.2.0 | BSD-3-Clause | git+https://github.com/lit/lit.git |
| `@lit/reactive-element` | 2.1.0 | BSD-3-Clause | git+https://github.com/lit/lit.git |
| `@lit/context` | 1.1.6 | BSD-3-Clause | git+https://github.com/lit/lit.git |
| `@lit-labs/signals` | 0.3.0 | BSD-3-Clause | git+https://github.com/lit/lit.git |
| `@lit-labs/ssr-dom-shim` | 1.3.0 | BSD-3-Clause | https://github.com/lit/lit.git |
| `signal-polyfill` | 0.2.2 | Apache-2.0 | https://github.com/proposal-signals/signal-polyfill.git |
| `signal-utils` | 0.21.1 | MIT | git@github.com:proposal-signals/signal-utils.git |
| `@preact/signals-core` | 1.14.4 | MIT | https://github.com/preactjs/signals |
| `zod` | 3.25.76 | MIT | git+https://github.com/colinhacks/zod.git |
| `zod-to-json-schema` | 3.25.2 | ISC | https://github.com/StefanTerdell/zod-to-json-schema |
| `validate-color` | 2.2.4 | MIT | https://github.com/dreamyguy/validate-color |
| `redos-detector` | 6.1.4 | MIT | git+https://github.com/tjenkinson/redos-detector.git |
| `regjsparser` | 0.13.0 | BSD-2-Clause | git+ssh://git@github.com/jviereck/regjsparser.git |
| `jsesc` | 3.1.0 | MIT | https://github.com/mathiasbynens/jsesc.git |

To rebuild, install `@a2ui/web_core` and `@a2ui/lit` 0.14.0 from npm and bundle
their entry points with esbuild (ESM, minified, legal comments kept); see
`A2UI_VERSIONS.json`.
