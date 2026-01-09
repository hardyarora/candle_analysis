-- PostgreSQL Schema for OANDA Candle Analysis Storage
-- Stores hourly snapshots of daily and weekly analysis results

-- Main table for storing analysis results
CREATE TABLE IF NOT EXISTS candle_analysis_snapshots (
    id SERIAL PRIMARY KEY,
    snapshot_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    timeframe VARCHAR(10) NOT NULL,  -- e.g., '1D', '2D', '3D', '4D', 'W', '2W', etc.
    granularity VARCHAR(10) NOT NULL,  -- 'D' for daily, 'W' for weekly
    analysis_data JSONB NOT NULL,  -- Full analysis results as JSON
    ignore_candles INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes for efficient querying
    CONSTRAINT unique_snapshot UNIQUE (snapshot_timestamp, timeframe)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_snapshot_timestamp ON candle_analysis_snapshots(snapshot_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_timeframe ON candle_analysis_snapshots(timeframe);
CREATE INDEX IF NOT EXISTS idx_granularity ON candle_analysis_snapshots(granularity);
CREATE INDEX IF NOT EXISTS idx_created_at ON candle_analysis_snapshots(created_at DESC);

-- GIN index for JSONB queries
CREATE INDEX IF NOT EXISTS idx_analysis_data_gin ON candle_analysis_snapshots USING GIN (analysis_data);

-- Table for tracking currency strength/weakness patterns
-- This extracts key patterns from the analysis_data for easier querying
CREATE TABLE IF NOT EXISTS currency_patterns (
    id SERIAL PRIMARY KEY,
    snapshot_id INTEGER REFERENCES candle_analysis_snapshots(id) ON DELETE CASCADE,
    snapshot_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    granularity VARCHAR(10) NOT NULL,
    instrument VARCHAR(20) NOT NULL,  -- e.g., 'GBPUSD', 'EURUSD'
    pattern_type VARCHAR(50) NOT NULL,  -- e.g., 'bullish engulfing + upclose', 'bearish engulfing + downclose'
    relation VARCHAR(100),  -- Full relation string from analysis
    color VARCHAR(10),  -- 'GREEN', 'RED', 'NEUTRAL'
    mc1_open NUMERIC(15, 5),
    mc1_high NUMERIC(15, 5),
    mc1_low NUMERIC(15, 5),
    mc1_close NUMERIC(15, 5),
    mc2_open NUMERIC(15, 5),
    mc2_high NUMERIC(15, 5),
    mc2_low NUMERIC(15, 5),
    mc2_close NUMERIC(15, 5),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for currency_patterns
CREATE INDEX IF NOT EXISTS idx_pattern_snapshot_id ON currency_patterns(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_pattern_timestamp ON currency_patterns(snapshot_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_pattern_timeframe ON currency_patterns(timeframe);
CREATE INDEX IF NOT EXISTS idx_pattern_instrument ON currency_patterns(instrument);
CREATE INDEX IF NOT EXISTS idx_pattern_type ON currency_patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_pattern_granularity ON currency_patterns(granularity);

-- Composite index for common queries
CREATE INDEX IF NOT EXISTS idx_pattern_timeframe_timestamp ON currency_patterns(timeframe, snapshot_timestamp DESC);

-- View for latest analysis by timeframe
CREATE OR REPLACE VIEW latest_analysis_by_timeframe AS
SELECT DISTINCT ON (timeframe)
    id,
    snapshot_timestamp,
    timeframe,
    granularity,
    analysis_data,
    ignore_candles,
    created_at
FROM candle_analysis_snapshots
ORDER BY timeframe, snapshot_timestamp DESC;

-- View for strength/weakness summary (currencies with bullish/bearish patterns)
CREATE OR REPLACE VIEW strength_weakness_summary AS
SELECT 
    snapshot_timestamp,
    timeframe,
    granularity,
    pattern_type,
    COUNT(*) as instrument_count,
    ARRAY_AGG(instrument ORDER BY instrument) as instruments
FROM currency_patterns
WHERE pattern_type IN (
    'bullish engulfing + upclose',
    'bullish engulfing',
    'bullish + upclose',
    'bearish engulfing + downclose',
    'bearish engulfing',
    'bearish + downclose'
)
GROUP BY snapshot_timestamp, timeframe, granularity, pattern_type
ORDER BY snapshot_timestamp DESC, timeframe, pattern_type;

-- Function to get latest snapshot for a timeframe
CREATE OR REPLACE FUNCTION get_latest_snapshot(p_timeframe VARCHAR)
RETURNS TABLE (
    id INTEGER,
    snapshot_timestamp TIMESTAMP WITH TIME ZONE,
    timeframe VARCHAR,
    granularity VARCHAR,
    analysis_data JSONB,
    ignore_candles INTEGER,
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        cas.id,
        cas.snapshot_timestamp,
        cas.timeframe,
        cas.granularity,
        cas.analysis_data,
        cas.ignore_candles,
        cas.created_at
    FROM candle_analysis_snapshots cas
    WHERE cas.timeframe = p_timeframe
    ORDER BY cas.snapshot_timestamp DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Function to get snapshots in a time range
CREATE OR REPLACE FUNCTION get_snapshots_range(
    p_timeframe VARCHAR,
    p_start_time TIMESTAMP WITH TIME ZONE,
    p_end_time TIMESTAMP WITH TIME ZONE
)
RETURNS TABLE (
    id INTEGER,
    snapshot_timestamp TIMESTAMP WITH TIME ZONE,
    timeframe VARCHAR,
    granularity VARCHAR,
    analysis_data JSONB,
    ignore_candles INTEGER,
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        cas.id,
        cas.snapshot_timestamp,
        cas.timeframe,
        cas.granularity,
        cas.analysis_data,
        cas.ignore_candles,
        cas.created_at
    FROM candle_analysis_snapshots cas
    WHERE cas.timeframe = p_timeframe
        AND cas.snapshot_timestamp >= p_start_time
        AND cas.snapshot_timestamp <= p_end_time
    ORDER BY cas.snapshot_timestamp DESC;
END;
$$ LANGUAGE plpgsql;

-- Table for storing strength-weakness categorization data
CREATE TABLE IF NOT EXISTS strength_weakness_snapshots (
    id SERIAL PRIMARY KEY,
    snapshot_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    period VARCHAR(10) NOT NULL,  -- 'daily', 'weekly', 'monthly'
    ignore_candles INTEGER DEFAULT 0,
    response_data JSONB NOT NULL,  -- Full response data as JSON
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes for efficient querying
    CONSTRAINT unique_strength_weakness_snapshot UNIQUE (snapshot_timestamp, period)
);

-- Indexes for strength_weakness_snapshots
CREATE INDEX IF NOT EXISTS idx_sw_snapshot_timestamp ON strength_weakness_snapshots(snapshot_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_sw_period ON strength_weakness_snapshots(period);
CREATE INDEX IF NOT EXISTS idx_sw_created_at ON strength_weakness_snapshots(created_at DESC);

-- GIN index for JSONB queries
CREATE INDEX IF NOT EXISTS idx_sw_response_data_gin ON strength_weakness_snapshots USING GIN (response_data);

-- Table for extracted currency strength/weakness data
CREATE TABLE IF NOT EXISTS currency_strength_weakness (
    id SERIAL PRIMARY KEY,
    snapshot_id INTEGER REFERENCES strength_weakness_snapshots(id) ON DELETE CASCADE,
    snapshot_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    period VARCHAR(10) NOT NULL,
    currency VARCHAR(10) NOT NULL,  -- Currency code (e.g., 'USD', 'EUR')
    tested_high_count INTEGER DEFAULT 0,
    tested_low_count INTEGER DEFAULT 0,
    strength NUMERIC(5, 4),  -- 0.0000 to 1.0000
    weakness NUMERIC(5, 4),  -- 0.0000 to 1.0000
    tested_high_instruments TEXT[],  -- Array of instrument names
    tested_low_instruments TEXT[],  -- Array of instrument names
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for currency_strength_weakness
CREATE INDEX IF NOT EXISTS idx_csw_snapshot_id ON currency_strength_weakness(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_csw_timestamp ON currency_strength_weakness(snapshot_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_csw_period ON currency_strength_weakness(period);
CREATE INDEX IF NOT EXISTS idx_csw_currency ON currency_strength_weakness(currency);
CREATE INDEX IF NOT EXISTS idx_csw_strength ON currency_strength_weakness(strength DESC);
CREATE INDEX IF NOT EXISTS idx_csw_weakness ON currency_strength_weakness(weakness DESC);

-- Composite index for common queries
CREATE INDEX IF NOT EXISTS idx_csw_period_timestamp ON currency_strength_weakness(period, snapshot_timestamp DESC);

-- View for latest strength-weakness by period
CREATE OR REPLACE VIEW latest_strength_weakness_by_period AS
SELECT DISTINCT ON (period)
    id,
    snapshot_timestamp,
    period,
    ignore_candles,
    response_data,
    created_at
FROM strength_weakness_snapshots
ORDER BY period, snapshot_timestamp DESC;

-- Function to get latest strength-weakness snapshot
CREATE OR REPLACE FUNCTION get_latest_strength_weakness(p_period VARCHAR)
RETURNS TABLE (
    id INTEGER,
    snapshot_timestamp TIMESTAMP WITH TIME ZONE,
    period VARCHAR,
    ignore_candles INTEGER,
    response_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        sws.id,
        sws.snapshot_timestamp,
        sws.period,
        sws.ignore_candles,
        sws.response_data,
        sws.created_at
    FROM strength_weakness_snapshots sws
    WHERE sws.period = p_period
    ORDER BY sws.snapshot_timestamp DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;
