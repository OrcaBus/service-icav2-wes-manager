// CommonJS bootstrap for the CDK app.
//
// On Node >= 20.6 the `ts-node` CLI registers Node's experimental ESM loader
// hooks, which makes Node resolve every import (including extensionless
// relative TypeScript imports and `source-map-support/register`) through the
// ESM resolver. That resolver requires explicit file extensions and therefore
// fails on this CommonJS-configured project.
//
// Registering ts-node programmatically and then `require`-ing the entrypoint
// keeps the whole module graph on the CommonJS loader, which resolves
// extensionless imports the way this project expects.
require('ts-node').register({
  transpileOnly: true,
  compilerOptions: {
    module: 'commonjs',
  },
});

require('./deploy.ts');
