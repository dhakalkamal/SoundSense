import 'react-native-gesture-handler';
import { View } from 'react-native';
import { useFonts, Domine_400Regular, Domine_700Bold } from '@expo-google-fonts/domine';
import AppNavigator from './src/navigation/AppNavigator';

export default function App() {
  const [fontsLoaded] = useFonts({ Domine_400Regular, Domine_700Bold });

  // Show a plain indigo splash while fonts load
  if (!fontsLoaded) return <View style={{ flex: 1, backgroundColor: '#1E1B4B' }} />;

  return <AppNavigator />;
}
