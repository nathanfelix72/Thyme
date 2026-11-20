import { Amplify } from "aws-amplify";

const region = import.meta.env.VITE_COGNITO_REGION || "us-west-1";
const userPoolId = import.meta.env.VITE_COGNITO_USER_POOL_ID || "";
const userPoolClientId = import.meta.env.VITE_COGNITO_CLIENT_ID || "";

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
