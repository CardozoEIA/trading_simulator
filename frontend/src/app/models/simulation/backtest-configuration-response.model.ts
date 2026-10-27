export interface BacktestConfigurationResponse {
    id: string
    asset: string
    start_date: string
    end_date: string
    initial_capital: number
    strategies: string[]
    ensemble_threshold?: number | null
    data_available: boolean
    records: number
}