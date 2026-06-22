import { initializeApp, getApps, FirebaseApp, FirebaseOptions } from "firebase/app";
import { getAuth as _getAuth, Auth } from "firebase/auth";
import { getFirestore as _getFirestore, Firestore } from "firebase/firestore";
import { getStorage as _getStorage, FirebaseStorage } from "firebase/storage";

let _app: FirebaseApp | null = null;
let _auth: Auth | null = null;
let _firestore: Firestore | null = null;
let _storage: FirebaseStorage | null = null;

function getConfig(): FirebaseOptions {
  const required = [
    ["apiKey", "NEXT_PUBLIC_FIREBASE_API_KEY"],
    ["authDomain", "NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN"],
    ["projectId", "NEXT_PUBLIC_FIREBASE_PROJECT_ID"],
    ["storageBucket", "NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET"],
    ["messagingSenderId", "NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID"],
    ["appId", "NEXT_PUBLIC_FIREBASE_APP_ID"],
  ] as const;

  const missing = required
    .filter(([, envKey]) => !process.env[envKey])
    .map(([, envKey]) => envKey);

  if (missing.length > 0) {
    throw new Error(
      `Firebase configuration incomplete. Missing environment variables:\n${missing.map((k) => `  - ${k}`).join("\n")}\n\nSet these in .env.local (see .env.local.example).`
    );
  }

  return {
    apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY!,
    authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN!,
    projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID!,
    storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET!,
    messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID!,
    appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID!,
  };
}

export function getFirebaseApp(): FirebaseApp {
  if (_app) return _app;
  _app = getApps().length > 0 ? getApps()[0] : initializeApp(getConfig());
  return _app;
}

export function getAuth(): Auth {
  if (_auth) return _auth;
  _auth = _getAuth(getFirebaseApp());
  return _auth;
}

export function getFirestore(): Firestore {
  if (_firestore) return _firestore;
  _firestore = _getFirestore(getFirebaseApp());
  return _firestore;
}

export function getStorage(): FirebaseStorage {
  if (_storage) return _storage;
  _storage = _getStorage(getFirebaseApp());
  return _storage;
}
