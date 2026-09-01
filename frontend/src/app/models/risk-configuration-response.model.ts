export interface RiskConfigurationResponse {
    id: string
    configuration_id: string
    stop_loss_percentage: number
    max_position_size: number
    max_drawdown: number
}