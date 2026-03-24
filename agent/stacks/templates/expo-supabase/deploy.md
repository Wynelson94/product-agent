# Expo + Supabase Deployment

## Pre-Deployment Checklist

1. App runs without errors: `npx expo start`
2. Environment variables configured
3. App icons and splash screen set
4. Bundle identifier configured for iOS/Android (mobile) or web config in app.json (web)
5. **For web deployments**: `babel.config.js` exists with `import.meta` transform
6. **For web deployments**: Web bundle passes validation (`npm run test:web-bundle`)

## EAS Build Setup

### 1. Install EAS CLI

```bash
npm install -g eas-cli
eas login
```

### 2. Configure EAS

```bash
eas build:configure
```

This creates `eas.json`:

```json
{
  "cli": {
    "version": ">= 5.0.0"
  },
  "build": {
    "development": {
      "developmentClient": true,
      "distribution": "internal"
    },
    "preview": {
      "distribution": "internal"
    },
    "production": {}
  },
  "submit": {
    "production": {}
  }
}
```

### 3. Configure Environment Variables

```bash
eas secret:create --name EXPO_PUBLIC_SUPABASE_URL --value "your_url"
eas secret:create --name EXPO_PUBLIC_SUPABASE_ANON_KEY --value "your_key"
```

## Building for Platforms

### iOS Build

```bash
# Development build (with dev client)
eas build --platform ios --profile development

# Production build
eas build --platform ios --profile production
```

Requirements:
- Apple Developer account ($99/year)
- App Store Connect configured

### Android Build

```bash
# Development build
eas build --platform android --profile development

# Production build (AAB for Play Store)
eas build --platform android --profile production
```

### Build Both Platforms

```bash
eas build --platform all --profile production
```

## App Store Submission

### iOS (App Store)

```bash
eas submit --platform ios
```

Requirements:
- App Store Connect app created
- App metadata filled out
- Screenshots uploaded

### Android (Google Play)

```bash
eas submit --platform android
```

Requirements:
- Google Play Developer account ($25 one-time)
- App created in Play Console
- Store listing completed

## OTA Updates (Expo Updates)

For JavaScript-only changes, use OTA updates:

```bash
# Publish update to production
eas update --branch production --message "Bug fixes"

# Publish to preview
eas update --branch preview --message "New feature"
```

## Web Deployment (Vercel)

For Expo apps targeting web, deploy as a static site to Vercel.

### Pre-Deploy Validation (CRITICAL)

```bash
# 1. Build the web export
npx expo export --platform web

# 2. Scan for import.meta (fatal on web — kills React hydration)
grep -r "import\.meta" dist/bundles/ --include="*.js" | grep -v "//" | grep -v "\*"

# 3. If import.meta found → STOP. Add babel.config.js transform (see scaffold template)
```

If `import.meta` is found in the bundle, **DO NOT DEPLOY**. The entire page will render
as static HTML with zero interactivity. Create DEPLOY_BLOCKED.md explaining the issue.

### Vercel Configuration

Create `vercel.json`:
```json
{
  "buildCommand": "npx expo export --platform web",
  "outputDirectory": "dist",
  "framework": null,
  "rewrites": [
    { "source": "/(.*)", "destination": "/" }
  ]
}
```

Add to `package.json` scripts:
```json
{
  "scripts": {
    "build:web": "npx expo export --platform web",
    "test:web-bundle": "npx expo export --platform web && ! grep -r 'import\\.meta' dist/bundles/ --include='*.js' -l"
  }
}
```

> **IMPORTANT**: Always run `npm run test:web-bundle` before deploying web builds.
> A passing result means no `import.meta` references in the bundle.

### Deploy

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel --prod
```

### Verify Web Deployment

After deployment:
1. Open the Vercel URL in Chrome
2. Open DevTools Console (F12)
3. Check for `SyntaxError` or `import.meta` errors
4. Verify interactive elements (buttons, forms) actually respond to clicks

## Supabase Configuration

### Deep Linking Setup

In Supabase Dashboard > Authentication > URL Configuration:

```
Site URL: myapp://
Additional Redirect URLs:
  - myapp://login-callback
  - exp://192.168.x.x:8081/--/login-callback (development)
```

### app.json Deep Link Config

```json
{
  "expo": {
    "scheme": "myapp",
    "ios": {
      "associatedDomains": ["applinks:your-supabase-url.supabase.co"]
    },
    "android": {
      "intentFilters": [
        {
          "action": "VIEW",
          "autoVerify": true,
          "data": [
            {
              "scheme": "myapp"
            }
          ],
          "category": ["BROWSABLE", "DEFAULT"]
        }
      ]
    }
  }
}
```

## Verification

### Development
- App loads on simulator/device
- Auth flow works
- Data syncs with Supabase

### Production
- Download from TestFlight/Internal Testing
- All features work
- Push notifications received
- Deep links work

## Troubleshooting

### Build failures
- Check EAS build logs
- Verify native dependencies compatible
- Check iOS/Android SDK versions

### Auth not persisting
- Verify AsyncStorage is installed
- Check Supabase client config

### Push notifications not working
- Verify credentials in EAS
- Check token saved to database
- Test with Expo push tool

### OTA updates not applying
- Verify `expo-updates` installed
- Check update channel matches
- Clear app cache and restart
