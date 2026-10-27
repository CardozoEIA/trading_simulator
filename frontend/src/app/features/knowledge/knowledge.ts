import { DatePipe } from '@angular/common';
import { Component, ElementRef, OnInit, inject, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { DocumentsService } from '@core/api/documents.service';
import { KnowledgeService } from '@core/api/knowledge.service';
import { Auth } from '@core/auth/auth';
import { ALLOWED_EXTENSIONS, KnowledgeDocument, MAX_FILE_BYTES } from '@models/knowledge/document.model';
import { KnowledgeSource } from '@models/knowledge/knowledge-chat.model';
import { Alert } from '@shared/ui/alert/alert';

interface ChatMessage {
  role: 'user' | 'assistant';
  text: string;
  refused?: boolean;
  isError?: boolean;
  pending?: boolean;
  sources?: KnowledgeSource[];
}

const SUGGESTIONS = [
  'What does the Sharpe ratio measure?',
  'How does a stop-loss work?',
  'What is the best recipe for sushi?',
];

@Component({
  selector: 'app-knowledge',
  imports: [FormsModule, DatePipe],
  templateUrl: './knowledge.html',
  styleUrl: './knowledge.css',
})
export class Knowledge implements OnInit {
  private documentsService = inject(DocumentsService);
  private knowledgeService = inject(KnowledgeService);
  private auth = inject(Auth);
  private router = inject(Router);
  private alert = inject(Alert);

  readonly accept = ALLOWED_EXTENSIONS.map((e) => '.' + e).join(',');
  readonly maxLength = 500;
  readonly suggestions = SUGGESTIONS;

  documents = signal<KnowledgeDocument[]>([]);
  loadingDocuments = signal(true);
  uploading = signal(false);
  dragging = signal(false);

  messages = signal<ChatMessage[]>([]);
  draft = signal('');
  sending = signal(false);

  private fileInput = viewChild<ElementRef<HTMLInputElement>>('fileInput');
  private scrollBox = viewChild<ElementRef<HTMLElement>>('scrollBox');

  ngOnInit(): void {
    this.loadDocuments();

    // The conversation is stored on the server: coming back later shows it again.
    this.knowledgeService.history().subscribe({
      next: (history) => {
        this.messages.set(
          history.messages.map((m) => ({
            role: m.role,
            text: m.content,
            refused: m.refused,
            sources: m.sources,
          })),
        );
        this.scrollToBottom();
      },
      error: () => {}, // history is optional: the chat still works without it
    });
  }

  // --- documents -----------------------------------------------------------

  loadDocuments(): void {
    this.documentsService.list().subscribe({
      next: (docs) => {
        this.documents.set(docs);
        this.loadingDocuments.set(false);
      },
      error: (error) => {
        this.loadingDocuments.set(false);
        this.alert.showApiError(error);
      },
    });
  }

  openPicker(): void {
    this.fileInput()?.nativeElement.click();
  }

  onFilesSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = ''; // lets the user pick the same file again
    if (file) this.upload(file);
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.dragging.set(true);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragging.set(false);
    const file = event.dataTransfer?.files?.[0];
    if (file) this.upload(file);
  }

  private upload(file: File): void {
    if (this.uploading()) return;

    const extension = file.name.split('.').pop()?.toLowerCase() ?? '';

    if (!ALLOWED_EXTENSIONS.includes(extension)) {
      this.alert.showError(`Unsupported file type. Allowed: ${ALLOWED_EXTENSIONS.join(', ')}.`);
      return;
    }

    if (file.size > MAX_FILE_BYTES) {
      this.alert.showError(`The file is larger than ${MAX_FILE_BYTES / (1024 * 1024)} MB.`);
      return;
    }

    this.uploading.set(true);

    this.documentsService.upload(file).subscribe({
      next: (doc) => {
        this.uploading.set(false);
        this.alert.showSuccess(`"${doc.filename}" was processed into ${doc.chunk_count} fragments.`);
        this.loadDocuments();
      },
      error: (error) => {
        this.uploading.set(false);
        this.alert.showApiError(error);
        this.loadDocuments(); // a failed document stays in the list so it can be deleted
      },
    });
  }

  async removeDocument(doc: KnowledgeDocument): Promise<void> {
    const confirmed = await this.alert.confirm(`Delete "${doc.filename}" and everything the agent learned from it?`);
    if (!confirmed) return;

    this.documentsService.remove(doc.id).subscribe({
      next: () => this.documents.update((list) => list.filter((d) => d.id !== doc.id)),
      error: (error) => this.alert.showApiError(error),
    });
  }

  formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  // --- chat ----------------------------------------------------------------

  send(text: string = this.draft()): void {
    const message = text.trim();
    if (!message || this.sending()) return;

    this.messages.update((list) => [
      ...list,
      { role: 'user', text: message },
      { role: 'assistant', text: '', pending: true },
    ]);
    this.draft.set('');
    this.sending.set(true);
    this.scrollToBottom();

    this.knowledgeService.ask(message).subscribe({
      next: (answer) => {
        this.replacePending({
          role: 'assistant',
          text: answer.answer,
          refused: answer.refused,
          sources: answer.sources,
        });
      },
      error: (error) => {
        const detail = typeof error?.error?.detail === 'string' ? error.error.detail : null;
        this.replacePending({
          role: 'assistant',
          text: detail ?? 'Something went wrong. Please try again.',
          isError: true,
        });
      },
    });
  }

  private replacePending(message: ChatMessage): void {
    this.messages.update((list) => [...list.slice(0, -1), message]);
    this.sending.set(false);
    this.scrollToBottom();
  }

  clearConversation(): void {
    this.knowledgeService.clearHistory().subscribe({
      next: () => this.messages.set([]),
      error: (error) => this.alert.showApiError(error),
    });
  }

  sourceLabel(source: KnowledgeSource): string {
    return source.page ? `${source.filename}, p. ${source.page}` : source.filename;
  }

  private scrollToBottom(): void {
    setTimeout(() => {
      const box = this.scrollBox()?.nativeElement;
      if (box) box.scrollTop = box.scrollHeight;
    });
  }

  // --- session -------------------------------------------------------------

  async onLogout(): Promise<void> {
    const confirmed = await this.alert.confirm('Do you want to log out?');
    if (confirmed) {
      this.auth.logout();
      this.router.navigate(['/']);
    }
  }
}
