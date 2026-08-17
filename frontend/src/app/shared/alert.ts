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
}
