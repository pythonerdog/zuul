const rewiredEsbuild = require("react-app-rewired-esbuild");

module.exports = function override(config, env) {
  // No additional config just want esbuild instead of babel
  return rewiredEsbuild()(config, env);
};

// use `customize-cra`
const { override } = require("customize-cra");

module.exports = override(rewiredEsbuild());
