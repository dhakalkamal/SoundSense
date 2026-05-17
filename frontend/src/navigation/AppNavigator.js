import React, { useState } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';
import OnboardingScreen from '../screens/OnboardingScreen';
import HomeScreen from '../screens/HomeScreen';

const Stack = createStackNavigator();

export default function AppNavigator() {
  const [onboarded, setOnboarded] = useState(false);
  const [profile, setProfile] = useState(null);

  const handleComplete = (data) => {
    setProfile(data);
    setOnboarded(true);
  };

  const handleLogout = () => {
    setProfile(null);
    setOnboarded(false);
  };

  return (
    <NavigationContainer>
      <Stack.Navigator screenOptions={{ headerShown: false, animationEnabled: true }}>
        {!onboarded ? (
          <Stack.Screen name="Onboarding">
            {() => <OnboardingScreen onComplete={handleComplete} />}
          </Stack.Screen>
        ) : (
          <Stack.Screen name="Home">
            {() => <HomeScreen profile={profile} onLogout={handleLogout} />}
          </Stack.Screen>
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
}
