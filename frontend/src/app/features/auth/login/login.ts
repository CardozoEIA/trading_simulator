import { Component, inject } from '@angular/core';
import { ReactiveFormsModule } from '@angular/forms';
import { FormGroup, FormControl, Validators } from '@angular/forms';
import { Auth } from '../../../core/auth';
import { Router, RouterLink } from '@angular/router';

@Component({
  selector: 'app-login',
  imports: [ ReactiveFormsModule, RouterLink ], // No es necesario incluir FormGroup o el resto, acá va lo que verá el html
  templateUrl: './login.html',
  styleUrl: './login.css',
})
export class Login {

  private auth = inject(Auth);
  private router = inject(Router);

  loginForm = new FormGroup({
    email: new FormControl('', [Validators.required, Validators.email]),
    password: new FormControl('', [Validators.required])
  })

  onSubmit(){
    this.auth.login(this.loginForm.value.email ?? '',
      this.loginForm.value.password ?? '').subscribe({
      next: (response) => { this.auth.saveToken(response.access_token);
                            this.router.navigate(['/dashboard']); },
      error: (error) => { console.log(error) }
    });
  }

}