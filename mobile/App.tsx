import "react-native-gesture-handler";
import { StatusBar } from "expo-status-bar";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { UploadScreen } from "./src/screens/UploadScreen";
import { ConnectScreen } from "./src/screens/ConnectScreen";
import { DraftListScreen } from "./src/screens/DraftListScreen";
import { DraftDetailScreen } from "./src/screens/DraftDetailScreen";
import { ServerProvider } from "./src/state/ServerContext";
import { RootStackParamList } from "./src/navigation/types";

const Stack = createNativeStackNavigator<RootStackParamList>();

export default function App() {
  return (
    <ServerProvider>
      <NavigationContainer>
        <StatusBar style="dark" />
        <Stack.Navigator initialRouteName="Connect">
          <Stack.Screen
            name="Connect"
            component={ConnectScreen}
            options={{ title: "Connect" }}
          />
          <Stack.Screen
            name="Drafts"
            component={DraftListScreen}
            options={{ title: "Drafts" }}
          />
          <Stack.Screen
            name="DraftDetail"
            component={DraftDetailScreen}
            options={{ title: "Draft" }}
          />
          <Stack.Screen
            name="Upload"
            component={UploadScreen}
            options={{ title: "Upload" }}
          />
        </Stack.Navigator>
      </NavigationContainer>
    </ServerProvider>
  );
}
