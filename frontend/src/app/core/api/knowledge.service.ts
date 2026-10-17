import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { KnowledgeAnswer, KnowledgeHistory } from '@models/knowledge/knowledge-chat.model';
import { environment } from '../../../environments/environment';

@Injectable({ providedIn: 'root' })
export class KnowledgeService {
  private http = inject(HttpClient);
  private baseUrl = environment.apiUrl;

  ask(message: string): Observable<KnowledgeAnswer> {
    return this.http.post<KnowledgeAnswer>(`${this.baseUrl}/knowledge/ask`, { message });
  }

  history(): Observable<KnowledgeHistory> {
    return this.http.get<KnowledgeHistory>(`${this.baseUrl}/knowledge/history`);
  }

  clearHistory(): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/knowledge/history`);
  }
}
