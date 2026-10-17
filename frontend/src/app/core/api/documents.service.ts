import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { KnowledgeDocument } from '@models/knowledge/document.model';
import { environment } from '../../../environments/environment';

@Injectable({ providedIn: 'root' })
export class DocumentsService {
  private http = inject(HttpClient);
  private baseUrl = environment.apiUrl;

  list(): Observable<KnowledgeDocument[]> {
    return this.http.get<KnowledgeDocument[]>(`${this.baseUrl}/documents`);
  }

  upload(file: File): Observable<KnowledgeDocument> {
    const form = new FormData();
    form.append('file', file, file.name);
    // No Content-Type header: the browser must add the multipart boundary itself.
    return this.http.post<KnowledgeDocument>(`${this.baseUrl}/documents`, form);
  }

  remove(id: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/documents/${id}`);
  }
}
