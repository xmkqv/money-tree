import { defineRailway, github, project, service } from "railway/iac";

const botWatchPatterns = [
  "/src/bot/**",
  "/src/cli/**",
  "/pyproject.toml",
  "/uv.lock",
  "/Dockerfile",
];

const webWatchPatterns = [
  "/src/ui/**",
  "/src/bot/export.py",
  "/src/bot/types.py",
  "/pyproject.toml",
  "/uv.lock",
  "/Dockerfile",
];

function requiredVariable(name: string): string {
  const value = process.env[name];
  if (value === undefined || value.trim() === "") {
    throw new Error(`${name} is required`);
  }
  return value;
}

function sealedVariable(name: string) {
  return { value: requiredVariable(name), isSealed: true };
}

export default defineRailway(() => {
  const moneyTree = github("xmkqv/money-tree", { checkSuites: false });

  const moneyTreeWeb = service("money-tree-web", {
    source: moneyTree,
    build: {
      watchPatterns: webWatchPatterns,
    },
    deploy: {
      healthcheckPath: "/healthz",
      healthcheckTimeout: 100,
      startCommand:
        'sh -c "exec uv run --locked --no-sync uvicorn ui.app:create_app --factory --workers 1 --host 0.0.0.0 --port $PORT"',
    },
    replicas: { "sfo": 1 },
    env: {
      APP_BASE_URL: requiredVariable("APP_BASE_URL"),
      RAILWAY_OAUTH_CLIENT_ID: sealedVariable("RAILWAY_OAUTH_CLIENT_ID"),
      RAILWAY_OAUTH_CLIENT_SECRET: sealedVariable("RAILWAY_OAUTH_CLIENT_SECRET"),
      RAILWAY_OAUTH_REDIRECT_URI: requiredVariable("RAILWAY_OAUTH_REDIRECT_URI"),
      ALLOWED_RAILWAY_EMAILS: requiredVariable("ALLOWED_RAILWAY_EMAILS"),
      SESSION_SECRET: sealedVariable("SESSION_SECRET"),
      SESSION_TTL_SECONDS: requiredVariable("SESSION_TTL_SECONDS"),
      ALPACA_IS_PAPER: requiredVariable("ALPACA_IS_PAPER"),
      ALPACA_API_KEY: sealedVariable("ALPACA_API_KEY"),
      ALPACA_API_SECRET: sealedVariable("ALPACA_API_SECRET"),
      FRACTIONAL_ORDERS: requiredVariable("FRACTIONAL_ORDERS"),
      POSITION_FRACTION_MAX: requiredVariable("POSITION_FRACTION_MAX"),
      RISK_PER_DAY_MAX: requiredVariable("RISK_PER_DAY_MAX"),
      RISK_PER_TRADE_MAX: requiredVariable("RISK_PER_TRADE_MAX"),
      STATE_EXPORT_SECRET: sealedVariable("STATE_EXPORT_SECRET"),
      PORT: requiredVariable("PORT"),
    },
  });
  const moneyTreeBot = service("money-tree-bot", {
    source: moneyTree,
    build: {
      watchPatterns: botWatchPatterns,
    },
    deploy: {
      startCommand:
        'sh -c "exec uv run --locked --no-sync mt trade --strategies $STRATEGIES"',
    },
    replicas: { "us-east4-eqdc4a": 1 },
    networking: { privateNetworkEndpoint: "money-tree" },
    env: {
      STRATEGIES: requiredVariable("STRATEGIES"),
      ALPACA_IS_PAPER: requiredVariable("ALPACA_IS_PAPER"),
      ALPACA_API_KEY: sealedVariable("ALPACA_API_KEY"),
      ALPACA_API_SECRET: sealedVariable("ALPACA_API_SECRET"),
      ALPACA_DATA_FEED: requiredVariable("ALPACA_DATA_FEED"),
      FRACTIONAL_ORDERS: requiredVariable("FRACTIONAL_ORDERS"),
      POSITION_FRACTION_MAX: requiredVariable("POSITION_FRACTION_MAX"),
      RISK_PER_DAY_MAX: requiredVariable("RISK_PER_DAY_MAX"),
      RISK_PER_TRADE_MAX: requiredVariable("RISK_PER_TRADE_MAX"),
      STATE_EXPORT_URL: requiredVariable("STATE_EXPORT_URL"),
      STATE_EXPORT_SECRET: sealedVariable("STATE_EXPORT_SECRET"),
    },
  });

  return project("money-tree", {
    resources: [moneyTreeWeb, moneyTreeBot],
  });
});
