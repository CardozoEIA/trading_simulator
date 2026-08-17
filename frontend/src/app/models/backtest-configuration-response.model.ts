export interface BacktestConfigurationResponse {
    id: string
    asset: string
    start_date: string
    end_date: string
    data_available: boolean
    records: number
}