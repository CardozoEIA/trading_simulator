export interface BacktestConfigurationResponse {
    id: string
    asset: string
    start_date: string
    end_date: string
    initial_capital: number
    strategies: string[]
    data_available: boolean
    records: number
}