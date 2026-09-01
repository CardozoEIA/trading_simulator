export interface BacktestConfigurationResponse {
    id: string
    asset: string
    start_date: string
    end_date: string
    initial_capital: number
    strategy: string
    data_available: boolean
    records: number
}