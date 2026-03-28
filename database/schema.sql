CREATE TABLE IF NOT EXISTS trades (
    trade_id            UUID PRIMARY KEY,
    timestamp           TIMESTAMPTZ NOT NULL,
    symbol              VARCHAR(20) NOT NULL,
    action              VARCHAR(10) NOT NULL CHECK (action IN ('BUY', 'SELL')),
    entry               NUMERIC(12, 4),
    stop_loss           NUMERIC(12, 4),
    target              NUMERIC(12, 4),
    rr_ratio            NUMERIC(6, 4),
    max_loss_pct        NUMERIC(6, 4),
    position_size_fraction NUMERIC(6, 4),
    features_vector     JSONB,
    result              VARCHAR(10) CHECK (result IN ('correct', 'wrong', 'pending')),
    rejection_reason    TEXT,
    updated_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS positions (
    position_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol              VARCHAR(20) NOT NULL,
    trade_id            UUID REFERENCES trades(trade_id),
    quantity            NUMERIC(12, 4),
    avg_entry           NUMERIC(12, 4),
    current_price       NUMERIC(12, 4),
    unrealised_pnl      NUMERIC(12, 4),
    status              VARCHAR(10) CHECK (status IN ('open', 'closed')),
    opened_at           TIMESTAMPTZ DEFAULT NOW(),
    closed_at           TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS weights (
    id                  SERIAL PRIMARY KEY,
    w_bias              NUMERIC(10, 6) NOT NULL,
    w_trend             NUMERIC(10, 6) NOT NULL,
    w_sentiment         NUMERIC(10, 6) NOT NULL,
    w_pattern           NUMERIC(10, 6) NOT NULL,
    w_volatility        NUMERIC(10, 6) NOT NULL,
    w_sr_signal         NUMERIC(10, 6) NOT NULL,
    w_volume            NUMERIC(10, 6) NOT NULL,
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS signals (
    signal_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol              VARCHAR(20) NOT NULL,
    action              VARCHAR(10) NOT NULL,
    confidence          NUMERIC(10, 6),
    probability_up      NUMERIC(10, 6),
    expected_value      NUMERIC(12, 4),
    pattern             VARCHAR(50),
    pattern_confidence  NUMERIC(6, 4),
    trend               VARCHAR(20),
    sentiment           VARCHAR(20),
    volume_signal       NUMERIC(10, 6),
    volatility          NUMERIC(12, 4),
    reason              TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
