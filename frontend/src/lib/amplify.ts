import { Amplify } from "aws-amplify";

// Defaults match Terraform / backend (SPA client id is public by design).
const region = import.meta.env.VITE_COGNITO_REGION || "us-west-1";
const userPoolId =
  import.meta.env.VITE_COGNITO_USER_POOL_ID || "us-west-1_Oqxx0Qvpk";
const userPoolClientId =
  import.meta.env.VITE_COGNITO_CLIENT_ID || "3aj94humt4rjn2gu9uklv9sd5j";

export const cognitoConfigured = Boolean(userPoolId && userPoolClientId);

if (cognitoConfigured) {
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId,
        userPoolClientId,
        loginWith: { email: true },
      },
    },
  });
}

export const cognitoConfig = { region, userPoolId, userPoolClientId };
