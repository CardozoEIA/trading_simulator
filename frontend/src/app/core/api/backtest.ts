import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Asset } from '@models/simulation/asset.model';
import { Strategy } from '@models/simulation/strategy.model';
import { BacktestConfigurationResponse } from '@models/simulation/backtest-configuration-response.model';
import { SetupParseResponse } from '@models/agent/setup.model';
import { environment } from '../../../environments/environment';

@Injectable({
  providedIn: 'root',
})
export class Backtest {

  private http = inject(HttpClient);
  private baseUrl = environment.apiUrl;

  public getAssets(){
    return this.http.get<Asset[]>(`${this.baseUrl}/backtest/assets`)
  }

  public getStrategies(){
    return this.http.get<Strategy[]>(`${this.baseUrl}/backtest/strategies`)
  }

  /**
   * `strategies` may mix built-in codes (SMA, RSI...) with custom ones (CUSTOM:<id>, US-21);
   * `ensembleThreshold` (US-24) only matters when two or more strategies are combined.
   */
  public configureBacktest(asset: string, startDate: string, endDate: string, initialCapital: number, strategies: string[],
                           ensembleThreshold: number | null = null){
    const customPrefix = 'CUSTOM:';
    return this.http.post<BacktestConfigurationResponse>(`${this.baseUrl}/backtest/configuration`, {
      asset: asset,
      start_date: startDate,
      end_date: endDate,
      initial_capital: initialCapital,
      strategies: strategies.filter(code => !code.startsWith(customPrefix)),
      custom_strategy_ids: strategies.filter(code => code.startsWith(customPrefix)).map(code => code.slice(customPrefix.length)),
      ensemble_threshold: ensembleThreshold
    })
  }

  /** US-29: reads a plain-language description into a configuration proposal. Saves nothing. */
  public parseSetup(description: string) {
    return this.http.post<SetupParseResponse>(`${this.baseUrl}/simulations/setup/parse`, { description });
  }
}
