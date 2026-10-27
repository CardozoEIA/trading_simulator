import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { CustomStrategy, CustomStrategyInput, ParameterCatalog } from '@models/simulation/custom-strategy.model';
import { environment } from '../../../environments/environment';

/** US-21: the student's custom strategies. */
@Injectable({
  providedIn: 'root',
})
export class CustomStrategies {

  private http = inject(HttpClient);
  private baseUrl = `${environment.apiUrl}/custom-strategies`;

  public list() {
    return this.http.get<CustomStrategy[]>(this.baseUrl);
  }

  /** Editable parameters of each base strategy, with defaults and limits. */
  public getParameters() {
    return this.http.get<ParameterCatalog>(`${this.baseUrl}/parameters`);
  }

  /** Checks a strategy without saving it. A 422 lists every problem found. */
  public validate(strategy: CustomStrategyInput) {
    return this.http.post<CustomStrategyInput>(`${this.baseUrl}/validate`, strategy);
  }

  public create(strategy: CustomStrategyInput) {
    return this.http.post<CustomStrategy>(this.baseUrl, strategy);
  }

  public update(id: string, strategy: CustomStrategyInput) {
    return this.http.put<CustomStrategy>(`${this.baseUrl}/${id}`, strategy);
  }

  public remove(id: string) {
    return this.http.delete<void>(`${this.baseUrl}/${id}`);
  }
}
