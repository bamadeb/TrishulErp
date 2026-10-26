import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  afterRenderEffect,
  computed,
  inject,
  input,
  signal,
} from '@angular/core';
import {
  AbstractControl,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import {
  MatError,
  MatFormField,
  MatHint,
  MatLabel,
  MatSuffix,
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatProgressBar } from '@angular/material/progress-bar';
import { Router } from '@angular/router';
import { AuthError, SignInStep } from '../auth-session';
import { AuthService } from '../auth.service';

type View =
  'sign-in' | 'new-password' | 'mfa-code' | 'forgot' | 'forgot-confirm';

/** Cognito's default policy, which the user pool should keep or tighten. */
const PASSWORD_MIN_LENGTH = 12;

/** Sign in, first-login password change, MFA code and forgot password, on one page (/login). */
@Component({
  selector: 'trishul-login-page',
  imports: [
    ReactiveFormsModule,
    MatFormField,
    MatLabel,
    MatInput,
    MatError,
    MatHint,
    MatSuffix,
    MatButton,
    MatIconButton,
    MatIcon,
    MatProgressBar,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './login.page.html',
  styleUrl: './login.page.scss',
})
export class LoginPage {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly fb = inject(NonNullableFormBuilder);

  /** Query parameters (router input binding). */
  readonly returnUrl = input<string>();
  readonly expired = input<string>();

  protected readonly usesPassword = this.auth.usesPassword;
  /** The Trishul user pool signs in by email; development sign-in uses the ERP username. */
  protected readonly usernameLabel = this.usesPassword ? 'Email' : 'Username';
  protected readonly passwordMinLength = PASSWORD_MIN_LENGTH;
  protected readonly view = signal<View>('sign-in');
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);
  protected readonly showPassword = signal(false);
  protected readonly codeDestination = signal('');
  protected readonly sessionEnded = computed(
    () => !!this.expired() && this.view() === 'sign-in' && !this.error(),
  );

  protected readonly signInForm = this.fb.group({
    username: ['', Validators.required],
    password: ['', this.usesPassword ? Validators.required : []],
  });
  protected readonly newPasswordForm = this.fb.group(
    { password: ['', newPasswordRules()], confirm: ['', Validators.required] },
    { validators: passwordsMatch },
  );
  protected readonly codeForm = this.fb.group({
    code: ['', [Validators.required, Validators.pattern(/^\d{6}$/)]],
  });
  protected readonly resetForm = this.fb.group(
    {
      code: ['', [Validators.required, Validators.pattern(/^\d{6}$/)]],
      password: ['', newPasswordRules()],
      confirm: ['', Validators.required],
    },
    { validators: passwordsMatch },
  );

  constructor() {
    // Each step starts in its first field, so keyboard and screen-reader users land on the new
    // step (instead of the autofocus attribute, which only works on page load).
    const host = inject<ElementRef<HTMLElement>>(ElementRef);
    afterRenderEffect(() => {
      this.view();
      host.nativeElement.querySelector<HTMLInputElement>('form input')?.focus();
    });
  }

  protected signIn(): void {
    if (this.invalid(this.signInForm)) return;
    const { username, password } = this.signInForm.getRawValue();
    this.run(async () => this.next(await this.auth.signIn(username, password)));
  }

  protected setNewPassword(): void {
    if (this.invalid(this.newPasswordForm)) return;
    const { password } = this.newPasswordForm.getRawValue();
    this.run(async () =>
      this.next(await this.auth.completeNewPassword(password)),
    );
  }

  protected confirmCode(): void {
    if (this.invalid(this.codeForm)) return;
    const { code } = this.codeForm.getRawValue();
    this.run(async () => this.next(await this.auth.confirmMfaCode(code)));
  }

  protected forgotPassword(): void {
    this.show('forgot');
  }

  protected sendResetCode(): void {
    const username = this.signInForm.controls.username;
    if (username.invalid) {
      username.markAsTouched();
      return;
    }
    this.run(async () => {
      this.codeDestination.set(
        await this.auth.sendPasswordResetCode(username.value),
      );
      this.show('forgot-confirm');
    });
  }

  protected resetPassword(): void {
    if (this.invalid(this.resetForm)) return;
    const { code, password } = this.resetForm.getRawValue();
    this.run(async () => {
      await this.auth.resetPassword(
        this.signInForm.controls.username.value,
        code,
        password,
      );
      this.signInForm.controls.password.reset();
      this.resetForm.reset();
      this.show('sign-in');
      this.notice.set('Password changed. Sign in with your new password.');
    });
  }

  protected backToSignIn(): void {
    this.show('sign-in');
  }

  private async next(step: SignInStep): Promise<void> {
    if (step === 'done') {
      await this.router.navigateByUrl(safeReturnUrl(this.returnUrl()));
    } else {
      this.show(step);
    }
  }

  private show(view: View): void {
    this.view.set(view);
    this.error.set(null);
    this.notice.set(null);
    this.showPassword.set(false);
  }

  private invalid(form: AbstractControl): boolean {
    form.markAllAsTouched();
    return form.invalid;
  }

  private run(action: () => Promise<void>): void {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set(null);
    this.notice.set(null);
    action()
      .catch((error: unknown) =>
        this.error.set(
          error instanceof AuthError
            ? error.message
            : 'Something went wrong. Try again.',
        ),
      )
      .finally(() => this.busy.set(false));
  }
}

function newPasswordRules() {
  return [Validators.required, Validators.minLength(PASSWORD_MIN_LENGTH)];
}

function passwordsMatch(group: AbstractControl): ValidationErrors | null {
  return group.get('password')?.value === group.get('confirm')?.value
    ? null
    : { mismatch: true };
}

/**
 * Only same-site paths: "/service/calls" is fine; "https://evil.example", "//evil.example" and
 * "/\evil.example" (both read as another site by browsers) fall back to the dashboard.
 */
export function safeReturnUrl(url: string | undefined): string {
  if (!url || !url.startsWith('/') || /^\/[/\\]/.test(url)) return '/';
  return url.startsWith('/login') ? '/' : url;
}
