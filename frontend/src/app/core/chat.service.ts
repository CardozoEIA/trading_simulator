import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Router } from '@angular/router';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import { ChatHistory, ChatResponse, ChatStreamEvent } from '../models/chat.model';
import { Auth } from './auth';

const STREAM_TIMEOUT_MS = 120_000;
const GENERIC_ERROR = 'Something went wrong. Please try again.';
const TIMEOUT_ERROR = 'The assistant took too long to respond. Please try again.';

@Injectable({ providedIn: 'root' })
export class ChatService {
  private http = inject(HttpClient);
  private auth = inject(Auth);
  private router = inject(Router);
  private baseUrl = environment.apiUrl;

  getHistory(simulationId: string): Observable<ChatHistory> {
    return this.http.get<ChatHistory>(`${this.baseUrl}/simulations/${simulationId}/chat/history`);
  }

  clearHistory(simulationId: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/simulations/${simulationId}/chat`);
  }

  /**
   * Sends a question and emits the answer as it is written.
   * HttpClient cannot read a response while it is still arriving, so this uses fetch and
   * adds the token by hand (the interceptor only sees HttpClient requests).
   */
  streamMessage(simulationId: string, message: string): Observable<ChatStreamEvent> {
    return new Observable<ChatStreamEvent>((subscriber) => {
      const controller = new AbortController();
      let timedOut = false;

      const timer = setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, STREAM_TIMEOUT_MS);

      const run = async () => {
        try {
          const token = this.auth.getToken();

          const response = await fetch(`${this.baseUrl}/simulations/${simulationId}/chat/stream`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Accept: 'text/event-stream',
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
            body: JSON.stringify({ message }),
            signal: controller.signal,
          });

          if (!response.ok || !response.body) {
            if (response.status === 401) {
              this.auth.logout();
              this.router.navigate(['/']);
            }

            const body = await response.json().catch(() => null);
            const detail = typeof body?.detail === 'string' ? body.detail : GENERIC_ERROR;
            subscriber.next({ type: 'error', detail });
            subscriber.complete();
            return;
          }

          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let buffer = '';

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n');

            let boundary = buffer.indexOf('\n\n');
            while (boundary !== -1) {
              const event = this.parseEvent(buffer.slice(0, boundary));
              buffer = buffer.slice(boundary + 2);
              if (event) subscriber.next(event);
              boundary = buffer.indexOf('\n\n');
            }
          }

          subscriber.complete();
        } catch {
          if (!subscriber.closed) {
            subscriber.next({ type: 'error', detail: timedOut ? TIMEOUT_ERROR : GENERIC_ERROR });
            subscriber.complete();
          }
        } finally {
          clearTimeout(timer);
        }
      };

      run();

      return () => {
        clearTimeout(timer);
        controller.abort();
      };
    });
  }

  private parseEvent(raw: string): ChatStreamEvent | null {
    let name = '';
    const dataLines: string[] = [];

    for (const line of raw.split('\n')) {
      if (line.startsWith('event:')) name = line.slice(6).trim();
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim());
    }

    if (!name || dataLines.length === 0) return null;

    try {
      const data = JSON.parse(dataLines.join('\n'));

      if (name === 'token') return { type: 'token', text: String(data.text ?? '') };
      if (name === 'done') return { type: 'done', response: data as ChatResponse };
      if (name === 'error') return { type: 'error', detail: String(data.detail ?? GENERIC_ERROR) };
    } catch {
      return null;
    }

    return null;
  }
}