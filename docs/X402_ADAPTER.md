# x402 payment adapter

Ledgato can govern x402 purchases through the existing enforcement gateway.

The x402 wallet credential belongs to the gateway process. An agent can request
an x402 purchase, but it cannot directly access the wallet or inject x402
payment headers. The gateway still applies the normal policy, delegated grant,
approval, idempotency, ledger, and post-action verification flow before or
after the adapter is invoked.

## Install

The dependency is optional:

    pip install -e ".[x402]"

The optional extra is currently bounded to x402 2.24+ and below the next major
version.

## Configuration

x402 remains disabled unless a wallet key is explicitly configured.

Required when enabled:

    LEDGATO_X402_EVM_PRIVATE_KEY=...
    LEDGATO_X402_ALLOWED_HOSTS=paid.example
    LEDGATO_X402_NETWORKS=eip155:84532

Optional:

    LEDGATO_X402_MAX_AMOUNT_PER_PAYMENT=$0.10
    LEDGATO_X402_TIMEOUT_SECONDS=30

For a zero-value proof, use an x402 resource on a test network and configure
only that network. Mainnet must be opted into explicitly, for example
eip155:8453 for Base mainnet.

Allowed hosts are exact hostnames. Redirects are disabled. The adapter rejects
caller-supplied Authorization, Cookie, PAYMENT-SIGNATURE, PAYMENT-RESPONSE, and
related protected headers before the payment client is called.

## Action

The first supported tool is x402.pay.

Example action payload:

    {
      "tool": "x402.pay",
      "params": {
        "url": "https://paid.example/resource",
        "method": "GET",
        "params": {"city": "Los Angeles"}
      },
      "domain": "paid.example",
      "impact": "write",
      "intent": "purchase a paid API response"
    }

GET and POST are supported in the first slice. POST bodies use the json field.

## Policy

A conservative initial policy keeps every payment behind approval:

    policies:
      - agent: agent-os
        allow_tools:
          - x402.pay
        approve_tools:
          - x402.pay
        impact_max: write

The adapter also applies the x402 SDK spend control configured by
LEDGATO_X402_MAX_AMOUNT_PER_PAYMENT. This is a hard adapter-level ceiling. A
future extension can add task/grant-specific monetary budgets to Ledgato's core
policy model; this first slice does not pretend those dynamic budget semantics
already exist.

## Evidence and current boundary

A successful x402.pay call is only recorded as executed when:

1. the final resource response is HTTP 2xx;
2. the x402 client can parse a successful settlement response; and
3. a PAYMENT-RESPONSE (or legacy X-PAYMENT-RESPONSE) header was present and its
   SHA-256 digest is recorded with the receipt.

Verification records the transaction, network, settlement success, and payment
response header digest. It deliberately reports onchain_finality_verified=false:
the first slice preserves the provider's x402 settlement evidence but does not
independently query a chain or facilitator to establish finality.

No wallet is funded or enabled by this code change alone.
