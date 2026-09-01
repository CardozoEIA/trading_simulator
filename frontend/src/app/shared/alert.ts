import { Injectable } from '@angular/core';
import Swal from 'sweetalert2';

@Injectable({
  providedIn: 'root',
})
export class Alert {

  public showError(message: string) {

    Swal.fire({
      icon: 'error',
      title: 'Something went wrong',
      text: message,
      background: '#F5F3EE',        // el hueso cálido, como fondo del popup
      color: '#0B1B2B',              // texto oscuro sobre ese fondo
      confirmButtonColor: '#C9A15C', // dorado para confirmar
    });
  }

  public showSuccess(message: string) {
    Swal.fire({
      icon: 'success',
      title: 'All set!',
      text: message,
      background: '#F5F3EE',        // el hueso cálido, como fondo del popup
      color: '#0B1B2B',              // texto oscuro sobre ese fondo
      confirmButtonColor: '#C9A15C', // dorado para confirmar
    })
  }

  public confirm(message: string): Promise<boolean> {
    return Swal.fire({
      title: 'Are you sure?',
      text: message,
      icon: 'warning',
      showCancelButton: true,
      confirmButtonColor: '#C9A15C',
      cancelButtonColor: '#5B7B8C',
      confirmButtonText: 'Yes!',
      cancelButtonText: 'Cancel',
      background: '#F5F3EE',
      color: '#0B1B2B',
    }).then((result) => result.isConfirmed);
  }

  private extractErrorMessage(error: any): string {
    const detail = error?.error?.detail;

    if (typeof detail === 'string') {
      return detail;
    }

    if (Array.isArray(detail)) {
      return detail
        .map((e: any) => e.msg ?? 'Validation error')
        .join('. ');
    }

    return 'An unexpected error occurred. Please try again.';
  }

  public showApiError(error: unknown): void {
    this.showError(this.extractErrorMessage(error));
  }
}
