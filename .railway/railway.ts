import { defineRailway, github, preserve, project, service } from "railway/iac";

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
      ALLOWED_RAILWAY_EMAILS: preserve(),
      ALPACA_API_KEY: preserve(),
      ALPACA_API_SECRET: preserve(),
      ALPACA_IS_PAPER: preserve(),
      APP_BASE_URL: preserve(),
      RAILWAY_OAUTH_CLIENT_ID: preserve(),
      RAILWAY_OAUTH_CLIENT_SECRET: preserve(),
      RAILWAY_OAUTH_REDIRECT_URI: preserve(),
      SESSION_SECRET: preserve(),
      STATE_EXPORT_SECRET: preserve(),
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
      ALPACA_API_KEY: preserve(),
      ALPACA_API_SECRET: preserve(),
      ALPACA_IS_PAPER: preserve(),
      ALPACA_LIVE_API_KEY: preserve(),
      ALPACA_LIVE_API_SECRET: preserve(),
      FRACTIONAL_ORDERS: preserve(),
      POSITION_FRACTION_MAX: preserve(),
      RISK_PER_DAY_MAX: preserve(),
      RISK_PER_TRADE_MAX: preserve(),
      STATE_EXPORT_SECRET: preserve(),
      STATE_EXPORT_URL: preserve(),
      STRATEGIES: "orb",
    },
  });

  return project("money-tree", {
    resources: [moneyTreeWeb, moneyTreeBot],
  });
});
