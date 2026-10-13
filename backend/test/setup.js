// Loaded with `node --import` before any test file, so config.js sees the test environment.
process.env.NODE_ENV = 'test'
process.env.SEED_PASSWORD = 'Test-password-1'
process.env.ALLOW_DEMO_RESET = 'false'
process.env.GOOGLE_CLIENT_ID = ''
process.env.GOOGLE_CLIENT_SECRET = ''
process.env.SMTP_HOST = ''
process.env.ANTHROPIC_API_KEY = ''
