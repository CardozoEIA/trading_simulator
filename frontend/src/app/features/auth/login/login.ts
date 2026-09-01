import { Component, inject } from '@angular/core';
import { ReactiveFormsModule } from '@angular/forms';
import { FormGroup, FormControl, Validators } from '@angular/forms';
import { Auth } from '../../../core/auth';
import { Router, RouterLink } from '@angular/router';
import { Alert } from '../../../shared/alert';
@Component({
  selector: 'app-login',
  imports: [ ReactiveFormsModule, RouterLink ],
  templateUrl: './login.html',
  styleUrl: './login.css',
})
export class Login {

  private auth = inject(Auth);
  private router = inject(Router);
  private alert = inject(Alert);
  submitted = false;

  loginForm = new FormGroup({
    email: new FormControl('', [Validators.required, Validators.email]),
    password: new FormControl('', [Validators.required])
  })

  onSubmit(){
    this.submitted = true;

    if (this.loginForm.invalid) {
      return;
    }

    this.auth.login(this.loginForm.value.email ?? '',
      this.loginForm.value.password ?? '').subscribe({
      next: (response) => { this.auth.saveToken(response.access_token);
                            this.router.navigate(['/dashboard']);
                           },
      error: (error) => { this.alert.showApiError(error) }
    });
  }
}