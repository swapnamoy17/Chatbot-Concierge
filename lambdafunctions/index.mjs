import { LexRuntimeV2Client, RecognizeTextCommand } from "@aws-sdk/client-lex-runtime-v2";
const lexClient = new LexRuntimeV2Client({ region: "us-east-1" });

let message = '';
let statusCode = 200;
    
//Event contains the user input message that we get from the API Gateway trigger.
export const handler = async (event) => {
    
    const params = {
        botAliasId: '', //LexV2 BotALiasID
        botId: '', //LexV2 BotId
        localeId: 'en_US',
        sessionId: '',
        text: event.messages[0].unstructured.text,
    };
    
    try {
        const command = new RecognizeTextCommand(params);
        const lexResponse = await lexClient.send(command);
        
        console.log("Response from Lex:", JSON.stringify(lexResponse, null, 2));
        message = lexResponse.messages[0].content;
    } catch (error) {
        statusCode = 400;
        message = "We are facing some issue.";
        console.error("Error calling Lex:", error);
    }
 
    const response = {
        statusCode: statusCode,
        messages: [
            {
              type: "unstructured",
              unstructured: {
               id: "temp",
               text: message,
               timestamp: "12/03/2024"
              }
            }
          ]
        ,
    };
  return response;
};