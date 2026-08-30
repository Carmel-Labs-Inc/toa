# toa-verify (JavaScript / Node 18+)

```bash
cd javascript
node src/cli.js ../examples/unsigned-example.json
```

```js
import { verifyDocument } from "toa-verify";

const result = verifyDocument(doc, { requireEmitter: "agentstatus" });
```
